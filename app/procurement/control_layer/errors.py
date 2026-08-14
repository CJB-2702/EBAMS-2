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
