"""Guard type: Validator. Shipment line quantities, and the part match on PO-line
assignment."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

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
    def check_quantity_floor(cls, *, line, new_quantity: Decimal) -> None:
        """Two hard stops on `quantity` (the shipped amount), mirroring
        PurchaseOrderLineValidator.check_quantity_floor on the Demand↔PO side
        (reallocation_resolution_portal.md §5/§7.11, Phase 5's mirror):

        1. Cannot drop below this line's own quantity_accepted — a physical
           fact; you cannot have accepted more than what arrived.
        2. Cannot drop below the sum of this line's LOCKED PO-line claims.
           Once the line is inspected, every active claim on it locks
           together (see PurchaseOrderShipmentLink's docstring — there is no
           per-claim inspection event to attribute, D90) — a source can never
           be cut below a locked total.
        """
        if line.quantity_accepted is not None and new_quantity < line.quantity_accepted:
            raise ProcurementValidationError(
                [
                    f"{line.quantity_accepted} has already been accepted against "
                    f"this line; the shipped quantity cannot be reduced to "
                    f"{new_quantity}."
                ]
            )

        locked_total = cls._locked_claims_total(line=line)
        if new_quantity < locked_total:
            raise ProcurementValidationError(
                [
                    f"{locked_total} is already locked against this line by "
                    f"inspected PO-line allocations; the shipped quantity "
                    f"cannot be reduced to {new_quantity}."
                ]
            )

    @staticmethod
    def _locked_claims_total(*, line) -> Decimal:
        return (
            line.purchase_order_links.filter(
                deleted_at__isnull=True, is_locked=True
            ).aggregate(total=Sum("quantity_allocated"))["total"]
            or Decimal("0")
        )

    @classmethod
    def check_split(cls, *, line, received_qty: Decimal) -> None:
        """FD-27 partial-receipt split: `received_qty` is the cumulative
        accepted+rejected total landed against this line so far. It must be a
        real, non-negative amount that does not exceed what was shipped —
        splitting off more "remaining" balance than the line ever carried
        would invent shipped quantity that never existed."""
        if received_qty is None or received_qty < 0:
            raise ProcurementValidationError(
                ["Received quantity for a split cannot be negative."]
            )
        if received_qty > line.quantity:
            raise ProcurementValidationError(
                [
                    f"Received quantity {received_qty} exceeds this line's shipped "
                    f"quantity of {line.quantity}."
                ]
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
