"""Guard type: StateMachine. Legal PurchaseOrder.status transitions (D27).

The same discipline as the demand-side axes, in a separate class because the
two lifecycles are genuinely independent: a PO is a commercial document with a
vendor, a demand is a need with a requester.

    Draft -> Placed -> Partially Received -> Received
    Draft -> Cancelled
    Placed -> Cancelled
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models import PurchaseOrderStatus

PURCHASE_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    PurchaseOrderStatus.DRAFT: frozenset(
        {PurchaseOrderStatus.PLACED, PurchaseOrderStatus.CANCELLED}
    ),
    PurchaseOrderStatus.PLACED: frozenset(
        {
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
            PurchaseOrderStatus.RECEIVED,
            PurchaseOrderStatus.CANCELLED,
        }
    ),
    # Partially Received can still be cancelled: a vendor discontinuing the
    # rest of an order after a part shipment is ordinary.
    PurchaseOrderStatus.PARTIALLY_RECEIVED: frozenset(
        {PurchaseOrderStatus.RECEIVED, PurchaseOrderStatus.CANCELLED}
    ),
    # A Received PO cannot be cancelled — the goods are here.
    PurchaseOrderStatus.RECEIVED: frozenset(),
    PurchaseOrderStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class PurchaseOrderVerdict:
    allowed: bool
    reason: str = ""


class PurchaseOrderStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> PurchaseOrderVerdict:
        if from_status == to_status:
            return PurchaseOrderVerdict(
                allowed=False, reason="The order is already in that state."
            )
        legal = PURCHASE_ORDER_TRANSITIONS.get(from_status)
        if legal is None:
            return PurchaseOrderVerdict(
                allowed=False, reason=f"Unknown purchase order status '{from_status}'."
            )
        if to_status not in legal:
            return PurchaseOrderVerdict(
                allowed=False,
                reason=f"A '{from_status}' purchase order cannot move to '{to_status}'.",
            )
        return PurchaseOrderVerdict(allowed=True)
