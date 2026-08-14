"""Handler: the splitting wizard's split operation.

SPLITTING INSTEAD OF A LINK TABLE. Each row's quantity IS the physical fact,
and the split rows sum to the original shipment by construction. A link table
with quantities creates two numbers for one fact and a reconciliation problem
between them — which the legacy design carried as
ArrivalLine.quantity_available_for_linking, a column that existed only to
describe a discrepancy the schema made possible.

split_from keeps the original line item reconstructible, so the audit trail
survives the split.

Note what the wizard's real work is: THE PO LOOKUP across a vendor's open
orders, not the arithmetic. Finding the right line is the hard part — see
PurchaseOrderLineSearch.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.procurement.control_layer.guards.package_line_guard import (
    PackageLineValidator,
)
from app.procurement.control_layer.managers.package_status_manager import (
    PackageStatusManager,
)
from app.procurement.control_layer.narrators.package_narrator import PackageNarrator
from app.procurement.control_layer.narrators.purchase_order_narrator import (
    PurchaseOrderNarrator,
)
from app.procurement.models import PackageLine


class PackageLineSplitHandler:
    @classmethod
    def split(
        cls,
        *,
        line: PackageLine,
        quantity: Decimal,
        purchase_order_line,
        actor=None,
    ) -> PackageLine:
        """Assign `quantity` of an arriving line to a chosen PO line.

        Creates a sibling row, reduces the original, and soft-deletes the
        original if it reaches zero. Repeat until the arriving quantity is
        fully assigned — a remainder may legitimately be left unassigned.
        """
        PackageLineValidator.check_split(package_line=line, quantity=quantity)
        PackageLineValidator.check_assignment(
            package_line=line, purchase_order_line=purchase_order_line
        )

        with transaction.atomic():
            sibling = PackageLine.objects.create(
                package=line.package,
                purchase_order_line=purchase_order_line,
                part_id=line.part_id,
                quantity=quantity,
                split_from=line,
                created_by=actor,
                updated_by=actor,
            )

            remaining = line.quantity - quantity
            if remaining > 0:
                line.quantity = remaining
                line.updated_by = actor
                line.save(update_fields=["quantity", "updated_by", "updated_at"])
            else:
                line.deleted_at = timezone.now()
                line.updated_by = actor
                line.save(
                    update_fields=["deleted_at", "updated_by", "updated_at"]
                )

            # D69: this is the ONLY place has_splits becomes True. A
            # full-quantity reassignment deliberately does not set it — the
            # package still has one row per physical line item and the bulk
            # planner can still represent it as one chip. An actual split
            # breaks that mapping, which is exactly what the flag locks out.
            package = line.package
            if not package.has_splits:
                package.has_splits = True
                package.updated_by = actor
                package.save(
                    update_fields=["has_splits", "updated_by", "updated_at"]
                )

            PackageStatusManager.refresh_mixed_po_assignments(
                package=package, actor=actor, commit=True
            )

            # D68: the split is always narrated on the package's OWN Event
            # first — that is the record's primary home now.
            PackageNarrator.post(
                package=line.package,
                message=PackageNarrator.line_split(
                    part_number=sibling.part.part_number,
                    quantity=quantity,
                    target_line_number=(
                        purchase_order_line.line_number if purchase_order_line else 0
                    ),
                ),
                actor=actor,
            )

            # A split landing on a DIFFERENT PO's line still additionally
            # narrates on that other PO's own Event — a split onto another
            # order's line is exactly the case where that order's history
            # would otherwise be silent. "Different" includes a package with
            # no header PO at all.
            if (
                purchase_order_line is not None
                and purchase_order_line.purchase_order_id
                != line.package.purchase_order_id
            ):
                PurchaseOrderNarrator.post(
                    purchase_order=purchase_order_line.purchase_order,
                    message=PurchaseOrderNarrator.package_line_split(
                        package_number=line.package.package_number,
                        part_number=sibling.part.part_number,
                        quantity=quantity,
                        target_line_number=purchase_order_line.line_number,
                    ),
                    actor=actor,
                )

        return sibling
