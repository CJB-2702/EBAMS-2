"""Manager: shipment line add / accept, and PO-line allocation (D90).

THE COPIED PO LINK IS A DEFAULT, NOT A BINDING. Allocating the whole arriving
line to the header PO's matching line at creation is what makes the common case
zero-effort: a box from one vendor against one order needs no per-line work at
all. Allocations are editable afterward, and editing them is expected — one
physical box routinely holds items from several orders to the same vendor.

The copy step resolves part -> PO line, which is only unambiguous while the
one-active-line-per-part rule holds (D58). With two active lines for the same
part on one PO the resolution is ambiguous and the line lands UNALLOCATED
rather than mis-allocated — the soft rule degrading gracefully, by design.

WHAT CHANGED IN D90. This manager used to own `reassign`, which moved a whole
arriving line from one PO line to another by rewriting an FK, with a separate
split handler for the partial case. Both are gone. There is one verb for
pointing arrived material at an order line — `allocate` — and it takes a
quantity, so the full and partial cases are the same code path rather than two
that drift. Un-pointing is `deallocate`, a soft delete of the link, and it
never touches the arriving line's own quantity.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.domain_structs.arrival_allocation import (
    allocated_by_shipment_line,
)
from app.procurement.control_layer.guards.shipment_line_guard import (
    ShipmentLineValidator,
)
from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.managers.shipment_status_manager import (
    ShipmentStatusManager,
)
from app.procurement.control_layer.narrators.shipment_narrator import ShipmentNarrator
from app.procurement.models import (
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    ShipmentLine,
)


class ShipmentLineManager:
    @classmethod
    def resolve_purchase_order_line(
        cls, *, purchase_order, part_id: int
    ) -> PurchaseOrderLine | None:
        """Find the header PO's single active line for this part.

        Returns None when there is no match (a vendor substitution, a wrong
        shipment, a bonus item) or when there is more than one (the D58 rule
        was breached). Both cases are recorded as unallocated, not refused —
        the allocation tool resolves them later.
        """
        candidates = list(
            PurchaseOrderLine.objects.filter(
                purchase_order=purchase_order,
                part_id=part_id,
                deleted_at__isnull=True,
            )[:2]
        )
        if len(candidates) == 1:
            return candidates[0]
        return None

    @classmethod
    def add_line(
        cls,
        *,
        shipment,
        part_id: int,
        quantity: Decimal,
        actor=None,
        purchase_order_line: PurchaseOrderLine | None = None,
        auto_link: bool = True,
        commit: bool = True,
    ) -> ShipmentLine:
        """`auto_link=False` suppresses copy-on-create.

        Copy-on-create exists because a receiver holding a box normally has not
        said which order lines it answers, so resolving part -> PO line is the
        best available guess. A caller who arrives WITH explicit allocations
        already decided — the create-shipment wizard is one — has no guess to
        improve on, and letting the copy run first would allocate the whole
        line to the matched PO line and leave no headroom for the allocations
        the user actually staged.
        """
        ShipmentLineValidator.check_new_line(quantity=quantity)

        if not auto_link:
            purchase_order_line = None
        elif purchase_order_line is None and shipment.purchase_order_id is not None:
            purchase_order_line = cls.resolve_purchase_order_line(
                purchase_order=shipment.purchase_order, part_id=part_id
            )

        with transaction.atomic():
            line = ShipmentLine.objects.create(
                shipment=shipment,
                part_id=part_id,
                quantity=quantity,
                created_by=actor,
                updated_by=actor,
            )
            # D82 node-init: every line gets its own fresh single-member graph
            # first — then, if a PO line was resolved or supplied, allocate()
            # merges it into that line's graph. Doing node-init unconditionally
            # rather than only for the unallocated case keeps this one code
            # path instead of two.
            GraphSummaryManager.initialize_node(entity=line, actor=actor)

            if purchase_order_line is not None:
                cls.allocate(
                    line=line,
                    purchase_order_line=purchase_order_line,
                    quantity=quantity,
                    actor=actor,
                    commit=commit,
                )
            else:
                ShipmentStatusManager.refresh_mixed_po_assignments(
                    shipment=shipment, actor=actor, commit=commit
                )
        return line

    # ------------------------------------------------------------------ #
    # Allocation
    # ------------------------------------------------------------------ #

    @classmethod
    def allocate(
        cls,
        *,
        line: ShipmentLine,
        purchase_order_line: PurchaseOrderLine,
        quantity: Decimal | None = None,
        actor=None,
        commit: bool = True,
    ) -> PurchaseOrderShipmentLink:
        """Point `quantity` of an arriving line at a PO line.

        `quantity=None` means "all of what is still unallocated", which is the
        one-box-one-order case and the overwhelming majority of calls.

        Re-allocating an existing pairing SETS the quantity rather than adding
        to it — the unique constraint means there is one row per pairing, so a
        second call is a correction of the first, not a second claim. Same
        rule PurchaseOrderDemandLinkManager applies on the demand side.
        """
        existing = PurchaseOrderShipmentLink.objects.filter(
            shipment_line=line,
            purchase_order_line=purchase_order_line,
            deleted_at__isnull=True,
        ).first()

        allocated_total = allocated_by_shipment_line(shipment_line_ids=[line.pk]).get(
            line.pk, Decimal("0")
        )
        # Exclude the row being rewritten from the ceiling, so raising an
        # existing allocation is checked against the same headroom as a new one.
        already_allocated = allocated_total - (
            existing.quantity_allocated if existing else Decimal("0")
        )
        if quantity is None:
            quantity = line.quantity - already_allocated

        ShipmentLineValidator.check_allocation(
            shipment_line=line,
            purchase_order_line=purchase_order_line,
            quantity=quantity,
            already_allocated=already_allocated,
        )

        with transaction.atomic():
            if existing is not None:
                existing.quantity_allocated = quantity
                existing.updated_by = actor
                existing.save(
                    update_fields=["quantity_allocated", "updated_by", "updated_at"]
                )
                link = existing
            else:
                link = PurchaseOrderShipmentLink.objects.create(
                    shipment_line=line,
                    purchase_order_line=purchase_order_line,
                    quantity_allocated=quantity,
                    created_by=actor,
                    updated_by=actor,
                )

            ShipmentStatusManager.refresh_mixed_po_assignments(
                shipment=line.shipment, actor=actor, commit=commit
            )

            # D82 merge: a new allocation may join two previously separate
            # graphs. BOTH sides are re-read — the shipment line because
            # node-init may have just created its graph in this transaction,
            # and the PO line because a caller may be holding an instance from
            # before an earlier merge repointed it (see deallocate's note).
            line.refresh_from_db(fields=["graph_id"])
            purchase_order_line.refresh_from_db(fields=["graph_id"])
            if line.graph_id != purchase_order_line.graph_id:
                GraphSummaryManager.merge(
                    graph_id_a=line.graph_id,
                    graph_id_b=purchase_order_line.graph_id,
                    actor=actor,
                )
        return link

    @classmethod
    def deallocate(
        cls,
        *,
        link: PurchaseOrderShipmentLink,
        actor=None,
        commit: bool = True,
    ) -> PurchaseOrderShipmentLink:
        """Release an allocation. Soft delete — the arriving line's own
        quantity is untouched, and the released amount returns to the
        unallocated remainder."""
        from django.utils import timezone

        purchase_order_line = link.purchase_order_line
        shipment = link.shipment_line.shipment

        with transaction.atomic():
            link.deleted_at = timezone.now()
            link.updated_by = actor
            link.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            ShipmentStatusManager.refresh_mixed_po_assignments(
                shipment=shipment, actor=actor, commit=commit
            )

            # D82 split: removing this edge may have severed the graph's only
            # bridge between the PO line's side and the shipment line's side.
            # Seeded from the PO line, since that edge is what just vanished.
            #
            # RE-READ FIRST. `purchase_order_line` reaches here through the
            # link's cached FK, which may be the very instance a caller passed
            # to allocate() — and merge() repoints rows with a bulk update, so
            # that instance's graph_id can name a graph that no longer has any
            # members. Splitting against it is a silent no-op: the seed fails
            # the membership check and the severed half is never detached.
            purchase_order_line.refresh_from_db(fields=["graph_id"])
            GraphSummaryManager.split_if_disconnected(
                graph_id=purchase_order_line.graph_id,
                seed_entity=purchase_order_line,
                actor=actor,
            )
        return link

    @classmethod
    def deallocate_all_for_line(
        cls, *, line: ShipmentLine, actor=None, commit: bool = True
    ) -> int:
        """Release every allocation on one arriving line.

        Used when the line itself is soft-deleted: a live allocation under a
        deleted line is exactly the orphan state ShipmentContext.delete already
        guards against for lines under a deleted shipment.
        """
        links = list(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line=line, deleted_at__isnull=True
            ).select_related("purchase_order_line", "shipment_line__shipment")
        )
        for link in links:
            cls.deallocate(link=link, actor=actor, commit=commit)
        return len(links)

    # ------------------------------------------------------------------ #
    # Acceptance
    # ------------------------------------------------------------------ #

    @classmethod
    def accept(
        cls,
        *,
        line: ShipmentLine,
        quantity_accepted: Decimal,
        actor=None,
        rejection_notes: str = "",
    ) -> ShipmentLine:
        """Record what actually survived the trip, separately from what the
        packing slip claimed.

        This does NOT touch PurchaseOrderDemandLink, and it does not touch
        PurchaseOrderShipmentLink either. There is no per-demand receipt
        attribution step and no per-allocation acceptance column (D55, D90) —
        inspection is physical and happens once, to the box. Per-PO-line and
        per-demand arrival are both derived; see arrival_allocation.py and
        PurchaseOrderFulfillmentStruct.

        Accepting records that goods arrived intact. It does not put them
        anywhere, because there is nowhere to put them: intake is not built.
        """
        ShipmentLineValidator.check_acceptance(quantity_accepted=quantity_accepted)

        line.quantity_accepted = quantity_accepted
        line.rejection_notes = rejection_notes
        line.updated_by = actor
        line.save(
            update_fields=[
                "quantity_accepted",
                "rejection_notes",
                "updated_by",
                "updated_at",
            ]
        )

        if quantity_accepted != line.quantity:
            ShipmentNarrator.post(
                shipment=line.shipment,
                message=ShipmentNarrator.line_accepted(
                    part_number=line.part.part_number,
                    quantity=line.quantity,
                    quantity_accepted=quantity_accepted,
                ),
                actor=actor,
            )
        return line
