"""Guard type: Validator. D58's soft one-active-line-per-part check, and the
accepted-quantity floor.

The duplicate-part check is a SOFT error by design: it returns a warning the UI
presents, and the control layer does not refuse. The rule is about pricing
simplicity (one part, one price, one line) rather than data integrity, so the
day split delivery dates or tiered pricing justify relaxing it, that should be
a guard change rather than a migration against live data. A duplicate that gets
through degrades gracefully — arriving shipment lines land unassigned rather
than mis-assigned.

The quantity floor is the ONE HARD STOP in line editing (D57). It is not a
policy: a quantity_ordered below what has already been accepted would simply be
false.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.domain_structs.arrival_allocation import (
    accepted_by_purchase_order_line,
)
from app.procurement.models import PurchaseOrderLine


@dataclass(frozen=True)
class DuplicatePartWarning:
    """Soft — the Buyer is told the part is already on this order and pointed
    at the existing line. Nothing hard-blocks."""

    existing_line_id: int
    existing_line_number: int
    message: str


class PurchaseOrderLineValidator:
    @classmethod
    def check_duplicate_part(
        cls, *, purchase_order, part_id: int, exclude_line_id: int | None = None
    ) -> DuplicatePartWarning | None:
        """Scoped to NON-DELETED lines, so cancel-and-replace legitimately
        leaves a deleted same-part line behind (D57's replacement path)."""
        qs = PurchaseOrderLine.objects.filter(
            purchase_order=purchase_order, part_id=part_id, deleted_at__isnull=True
        )
        if exclude_line_id is not None:
            qs = qs.exclude(pk=exclude_line_id)
        existing = qs.first()
        if existing is None:
            return None
        return DuplicatePartWarning(
            existing_line_id=existing.pk,
            existing_line_number=existing.line_number,
            message=(
                f"This part is already on line {existing.line_number} of this order. "
                f"Add the quantity there rather than opening a second line."
            ),
        )

    @classmethod
    def check_quantity_floor(cls, *, line, new_quantity_ordered: Decimal) -> None:
        """Hard stop: a line's quantity_ordered cannot drop below what has
        already been accepted against it in shipments.

        The accepted figure is derived from allocation shares since D90, so on
        a multi-allocation arriving line this floor can sit at a fractional
        value. That is the honest number and the right one to guard with — the
        alternative, rounding it down, would let a Buyer shrink a line below
        material that genuinely landed against it.
        """
        accepted = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line.pk]
        ).get(line.pk, Decimal("0"))

        if new_quantity_ordered < accepted:
            raise ProcurementValidationError(
                [
                    f"{accepted} has already been accepted against this line; "
                    f"the ordered quantity cannot be reduced to "
                    f"{new_quantity_ordered}."
                ]
            )

    @classmethod
    def check_new_line(cls, *, quantity_ordered: Decimal, unit_cost: Decimal) -> None:
        errors: list[str] = []
        if quantity_ordered is None or quantity_ordered <= 0:
            errors.append("Ordered quantity must be greater than zero.")
        if unit_cost is None or unit_cost < 0:
            errors.append("Unit cost cannot be negative.")
        if errors:
            raise ProcurementValidationError(errors)
