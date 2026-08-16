"""Guard type: Validator. Shipment line quantities, and the part match on PO-line
assignment."""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError


class ShipmentLineValidator:
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
    def check_assignment(cls, *, shipment_line, purchase_order_line) -> None:
        """A shipment line may only be allocated to a PO line for the same
        part."""
        if purchase_order_line is None:
            return
        if shipment_line.part_id != purchase_order_line.part_id:
            raise ProcurementValidationError(
                [
                    f"This shipment line is for a different part than purchase order "
                    f"line {purchase_order_line.line_number}."
                ]
            )

    @classmethod
    def check_allocation(
        cls,
        *,
        shipment_line,
        purchase_order_line,
        quantity: Decimal,
        already_allocated: Decimal,
    ) -> None:
        """The cap that makes the link table honest (D90).

        `already_allocated` is the line's active allocation total EXCLUDING the
        row being written, so editing an existing allocation upward is checked
        against the same ceiling as adding a new one.

        THIS ONE BLOCKS, unlike most guards in this app (D13 prefers reporting
        over blocking). Over-allocation is not a business event a manager needs
        to see — it is a claim that more of a box was assigned than was in the
        box, and permitting it reintroduces exactly the two-numbers-for-one-fact
        problem the old splitting design existed to avoid. Over-RECEIPT against
        a PO line is a different thing entirely and stays legal and merely
        flagged: vendors do over-ship.
        """
        cls.check_assignment(
            shipment_line=shipment_line, purchase_order_line=purchase_order_line
        )
        if quantity is None or quantity <= 0:
            raise ProcurementValidationError(
                ["Allocated quantity must be greater than zero."]
            )
        remaining = shipment_line.quantity - already_allocated
        if quantity > remaining:
            raise ProcurementValidationError(
                [
                    f"Cannot allocate {quantity} — only {remaining} of this "
                    f"arriving line's {shipment_line.quantity} is still "
                    f"unallocated."
                ]
            )
