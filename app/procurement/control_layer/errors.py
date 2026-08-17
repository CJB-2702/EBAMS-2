"""Shared control-layer exceptions for the procurement app.

One module so every guard, manager, and factory raises the *same* classes
rather than each declaring an identical copy.
"""

from __future__ import annotations


class ProcurementValidationError(Exception):
    """Input or invariant check failed at a boundary."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class TransitionRefused(ProcurementValidationError):
    """A state transition was refused by a guard.

    Distinct from a plain validation error because refusals carry a next
    action: the message names the thing that must happen first (cancel PO
    #1234, get the demand approved), never a generic failure.
    """


class AllocationCapExceeded(ProcurementValidationError):
    """A demand allocation exceeded the demand's outstanding requested quantity.

    NOT a flat failure — D28 requires the caller be offered an explicit choice:
    raise the demand's quantity_requested to cover the allocation, or leave the
    excess unallocated on the PO line. The exception carries the numbers needed
    to present that choice.

    binary_allocation=True means the allocation must be all-or-nothing: the
    user must allocate the entire outstanding amount or not allocate at all.
    """

    def __init__(
        self,
        *,
        demand_id: int,
        quantity_requested,
        purchased_qty,
        outstanding,
        attempted,
        binary_allocation: bool = False,
    ) -> None:
        self.demand_id = demand_id
        self.quantity_requested = quantity_requested
        self.purchased_qty = purchased_qty
        self.outstanding = outstanding
        self.attempted = attempted
        self.binary_allocation = binary_allocation

        if binary_allocation:
            msg = (
                f"Demand #{demand_id} must be allocated in full (all {outstanding}) "
                f"or not at all. Partial allocation is not allowed — if you cannot "
                f"purchase the full amount, allocate it to a future order instead."
            )
        else:
            msg = (
                f"Demand #{demand_id} has {outstanding} outstanding "
                f"({quantity_requested} requested, {purchased_qty} already on order) "
                f"but {attempted} was allocated. Raise the request to cover it, or "
                f"leave the excess unallocated on the line."
            )
        super().__init__([msg])


class CrossOrderAllocationExceeded(ProcurementValidationError):
    """reallocation_resolution_portal.md §10: a new/grown claim would push a
    demand's total active claims — summed across EVERY order it touches, not
    just the one on screen — beyond its requested quantity.

    Deliberately NOT the same choice AllocationCapExceeded offers: §10 rule 1
    is explicit that "raise the requested quantity" is not offered for this
    conflict, even though that escape hatch exists for the same-line cap case
    right next to it. This is always a hard stop, naming the conflicting
    order (rule 2) so the caller can render a direct link to it.
    """

    def __init__(
        self,
        *,
        demand_id: int,
        quantity_requested,
        total_across_orders,
        attempted,
        conflicting_purchase_order_id: int,
        conflicting_po_number: str,
        conflicting_line_number: int,
    ) -> None:
        self.demand_id = demand_id
        self.quantity_requested = quantity_requested
        self.total_across_orders = total_across_orders
        self.attempted = attempted
        self.conflicting_purchase_order_id = conflicting_purchase_order_id
        self.conflicting_po_number = conflicting_po_number
        self.conflicting_line_number = conflicting_line_number
        msg = (
            f"Demand #{demand_id} already has {total_across_orders} allocated "
            f"across every order it touches (requested {quantity_requested}); "
            f"{attempted} here would exceed that. It already carries a claim "
            f"on {conflicting_po_number} line {conflicting_line_number} — "
            f"reduce or remove that claim first."
        )
        super().__init__([msg])


class ReallocationRequired(ProcurementValidationError):
    """A PO line quantity reduction leaves a shortfall Phase 1's silent paths
    cannot resolve (2+ active claims short, or the sole claim locked).

    NOT a flat failure — reallocation_resolution_portal.md §5 requires the
    caller open the Reallocation Portal instead of refusing outright. Carries
    what the Portal needs to seed its session draft without a second query.
    """

    def __init__(
        self,
        *,
        line_id: int,
        new_quantity_ordered,
        total_claimed,
        locked_total,
        claim_count: int,
    ) -> None:
        self.line_id = line_id
        self.new_quantity_ordered = new_quantity_ordered
        self.total_claimed = total_claimed
        self.locked_total = locked_total
        self.claim_count = claim_count
        msg = (
            f"Reducing line #{line_id} to {new_quantity_ordered} leaves "
            f"{total_claimed} claimed across {claim_count} demand(s) "
            f"({locked_total} of it locked). Resolve through the Reallocation "
            f"Portal."
        )
        super().__init__([msg])


class PackageReallocationRequired(ProcurementValidationError):
    """The Package↔PO Domain mirror of ReallocationRequired (Phase 5): a
    shipment line's shipped-quantity reduction leaves a shortfall against its
    PurchaseOrderShipmentLink claims that Phase 5's silent paths cannot
    resolve. Deliberately a separate class from ReallocationRequired — the
    two domains never share state (§7.7), including their error types.
    """

    def __init__(
        self,
        *,
        shipment_line_id: int,
        new_quantity,
        total_claimed,
        locked_total,
        claim_count: int,
    ) -> None:
        self.shipment_line_id = shipment_line_id
        self.new_quantity = new_quantity
        self.total_claimed = total_claimed
        self.locked_total = locked_total
        self.claim_count = claim_count
        msg = (
            f"Reducing shipment line #{shipment_line_id} to {new_quantity} "
            f"leaves {total_claimed} claimed across {claim_count} PO-line "
            f"allocation(s) ({locked_total} of it locked). Resolve through the "
            f"Reallocation Portal."
        )
        super().__init__([msg])
