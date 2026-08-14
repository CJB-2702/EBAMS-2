"""Manager: shipment line add / accept / reassign.

THE COPIED PO LINK IS A DEFAULT, NOT A BINDING. Copying the header's PO link at
creation is what makes the common case zero-effort: a box from one vendor
against one order needs no per-line assignment at all. Lines are reassignable
afterward, and reassignment is expected — one physical box routinely holds
items from several orders to the same vendor.

The copy step resolves part -> PO line, which is only unambiguous while the
one-active-line-per-part rule holds (D58). With two active lines for the same
part on one PO the resolution is ambiguous and the line lands UNASSIGNED rather
than mis-assigned — the soft rule degrading gracefully, by design.
"""

from __future__ import annotations

from decimal import Decimal

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
from app.procurement.models import ShipmentLine, PurchaseOrderLine


class ShipmentLineManager:
    @classmethod
    def resolve_purchase_order_line(
        cls, *, purchase_order, part_id: int
    ) -> PurchaseOrderLine | None:
        """Find the header PO's single active line for this part.

        Returns None when there is no match (a vendor substitution, a wrong
        shipment, a bonus item) or when there is more than one (the D58 rule
        was breached). Both cases are recorded as unassigned, not refused — the
        splitting wizard resolves them later.
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
        commit: bool = True,
    ) -> ShipmentLine:
        ShipmentLineValidator.check_new_line(quantity=quantity)

        if purchase_order_line is None:
            purchase_order_line = cls.resolve_purchase_order_line(
                purchase_order=shipment.purchase_order, part_id=part_id
            )

        line = ShipmentLine.objects.create(
            shipment=shipment,
            purchase_order_line=purchase_order_line,
            part_id=part_id,
            quantity=quantity,
            created_by=actor,
            updated_by=actor,
        )
        # D82 node-init: every line gets its own fresh single-member graph
        # first — then, if it landed on a PO line (the copied-header default,
        # or an explicit assignment), merge into that line's graph. Doing
        # node-init unconditionally rather than only for the unassigned case
        # keeps this one code path instead of two.
        GraphSummaryManager.initialize_node(entity=line, actor=actor)
        if purchase_order_line is not None:
            line.refresh_from_db(fields=["graph_id"])
            if line.graph_id != purchase_order_line.graph_id:
                GraphSummaryManager.merge(
                    graph_id_a=line.graph_id,
                    graph_id_b=purchase_order_line.graph_id,
                    actor=actor,
                )
        ShipmentStatusManager.refresh_mixed_po_assignments(
            shipment=shipment, actor=actor, commit=commit
        )
        return line

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

        This does NOT touch PurchaseOrderDemandLink. There is no per-demand
        receipt attribution step and no quantity_received column on the
        allocation row (D55) — per-demand arrival is derived, under the rule in
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

    @classmethod
    def reassign(
        cls,
        *,
        line: ShipmentLine,
        purchase_order_line: PurchaseOrderLine | None,
        actor=None,
        commit: bool = True,
    ) -> ShipmentLine:
        """Point a whole line at a different PO line — the degenerate case of
        splitting: full quantity, no new row."""
        ShipmentLineValidator.check_assignment(
            shipment_line=line, purchase_order_line=purchase_order_line
        )
        old_purchase_order_line = line.purchase_order_line
        line.purchase_order_line = purchase_order_line
        line.updated_by = actor
        line.save(
            update_fields=["purchase_order_line", "updated_by", "updated_at"]
        )
        ShipmentStatusManager.refresh_mixed_po_assignments(
            shipment=line.shipment, actor=actor, commit=commit
        )

        # D82 split: reassigning away from the old PO line may have severed
        # that graph's only bridge to this shipment line (and whatever is
        # behind it). Checked against the OLD line's graph, seeded from the
        # old line itself, since that edge is what just disappeared.
        if old_purchase_order_line is not None and (
            purchase_order_line is None
            or purchase_order_line.pk != old_purchase_order_line.pk
        ):
            GraphSummaryManager.split_if_disconnected(
                graph_id=old_purchase_order_line.graph_id,
                seed_entity=old_purchase_order_line,
                actor=actor,
            )

        # D82 merge: reassigning onto a NEW PO line may join two previously
        # separate graphs. Re-fetched because the split above may already
        # have moved this line onto a fresh graph of its own.
        if purchase_order_line is not None:
            line.refresh_from_db(fields=["graph_id"])
            if line.graph_id != purchase_order_line.graph_id:
                GraphSummaryManager.merge(
                    graph_id_a=line.graph_id,
                    graph_id_b=purchase_order_line.graph_id,
                    actor=actor,
                )
        return line
