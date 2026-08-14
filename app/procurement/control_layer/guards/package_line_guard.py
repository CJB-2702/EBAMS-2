"""Guard type: Validator. Package line quantities, and the part match on PO-line
assignment."""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError


class PackageLineValidator:
    @classmethod
    def check_new_line(cls, *, quantity: Decimal) -> None:
        if quantity is None or quantity <= 0:
            raise ProcurementValidationError(
                ["Shipped quantity must be greater than zero."]
            )

    @classmethod
    def check_acceptance(cls, *, quantity_accepted: Decimal) -> None:
        """quantity_accepted may be less than, equal to, or GREATER THAN the
        shipped quantity — vendors over-ship, and the honest record says so.
        Only >= 0 is enforced."""
        if quantity_accepted is None or quantity_accepted < 0:
            raise ProcurementValidationError(
                ["Accepted quantity cannot be negative."]
            )

    @classmethod
    def check_assignment(cls, *, package_line, purchase_order_line) -> None:
        """A package line may only be pointed at a PO line for the same part."""
        if purchase_order_line is None:
            return
        if package_line.part_id != purchase_order_line.part_id:
            raise ProcurementValidationError(
                [
                    f"This package line is for a different part than purchase order "
                    f"line {purchase_order_line.line_number}."
                ]
            )

    @classmethod
    def check_split(cls, *, package_line, quantity: Decimal) -> None:
        if quantity is None or quantity <= 0:
            raise ProcurementValidationError(
                ["Split quantity must be greater than zero."]
            )
        if quantity > package_line.quantity:
            raise ProcurementValidationError(
                [
                    f"Cannot split {quantity} from a line carrying only "
                    f"{package_line.quantity}."
                ]
            )
