"""Manager: package line add / accept / reassign.

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

from app.procurement.control_layer.guards.package_line_guard import (
    PackageLineValidator,
)
from app.procurement.control_layer.managers.package_status_manager import (
    PackageStatusManager,
)
from app.procurement.control_layer.narrators.package_narrator import PackageNarrator
from app.procurement.models import PackageLine, PurchaseOrderLine


class PackageLineManager:
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
        package,
        part_id: int,
        quantity: Decimal,
        actor=None,
        purchase_order_line: PurchaseOrderLine | None = None,
        commit: bool = True,
    ) -> PackageLine:
        PackageLineValidator.check_new_line(quantity=quantity)

        if purchase_order_line is None:
            purchase_order_line = cls.resolve_purchase_order_line(
                purchase_order=package.purchase_order, part_id=part_id
            )

        line = PackageLine.objects.create(
            package=package,
            purchase_order_line=purchase_order_line,
            part_id=part_id,
            quantity=quantity,
            created_by=actor,
            updated_by=actor,
        )
        PackageStatusManager.refresh_mixed_po_assignments(
            package=package, actor=actor, commit=commit
        )
        return line

    @classmethod
    def accept(
        cls,
        *,
        line: PackageLine,
        quantity_accepted: Decimal,
        actor=None,
        rejection_notes: str = "",
    ) -> PackageLine:
        """Record what actually survived the trip, separately from what the
        packing slip claimed.

        This does NOT touch PurchaseOrderDemandLink. There is no per-demand
        receipt attribution step and no quantity_received column on the
        allocation row (D55) — per-demand arrival is derived, under the rule in
        PurchaseOrderFulfillmentStruct.

        Accepting records that goods arrived intact. It does not put them
        anywhere, because there is nowhere to put them: intake is not built.
        """
        PackageLineValidator.check_acceptance(quantity_accepted=quantity_accepted)

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
            PackageNarrator.post(
                package=line.package,
                message=PackageNarrator.line_accepted(
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
        line: PackageLine,
        purchase_order_line: PurchaseOrderLine | None,
        actor=None,
        commit: bool = True,
    ) -> PackageLine:
        """Point a whole line at a different PO line — the degenerate case of
        splitting: full quantity, no new row."""
        PackageLineValidator.check_assignment(
            package_line=line, purchase_order_line=purchase_order_line
        )
        line.purchase_order_line = purchase_order_line
        line.updated_by = actor
        line.save(
            update_fields=["purchase_order_line", "updated_by", "updated_at"]
        )
        PackageStatusManager.refresh_mixed_po_assignments(
            package=line.package, actor=actor, commit=commit
        )
        return line
