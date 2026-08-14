"""Guard type: StateMachine. Legal PurchaseOrder.approval_state transitions
(D71/D76) — a separate axis from status (see purchase_order_state_guard).

    Unsubmitted -> Pending Approval -> Approved
         |               |
       Denied / Cancelled (reachable from either non-terminal state, any time)

Approved is NOT revocable through this axis — an approved order is cancelled
through status instead, never demoted back through this one.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models.purchasing.enums import (
    APPROVAL_STATE_UNSET,
    PurchaseOrderApprovalState,
)

APPROVAL_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    APPROVAL_STATE_UNSET: frozenset({PurchaseOrderApprovalState.PENDING_APPROVAL}),
    PurchaseOrderApprovalState.PENDING_APPROVAL: frozenset(
        {
            PurchaseOrderApprovalState.APPROVED,
            PurchaseOrderApprovalState.DENIED,
            PurchaseOrderApprovalState.CANCELLED,
        }
    ),
    # Denied may be resubmitted for another look.
    PurchaseOrderApprovalState.DENIED: frozenset(
        {
            PurchaseOrderApprovalState.PENDING_APPROVAL,
            PurchaseOrderApprovalState.CANCELLED,
        }
    ),
    # Terminal through this axis.
    PurchaseOrderApprovalState.APPROVED: frozenset(),
    PurchaseOrderApprovalState.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class PurchaseOrderApprovalVerdict:
    allowed: bool
    reason: str = ""


class PurchaseOrderApprovalStateMachine:
    @classmethod
    def check(cls, *, from_state: str, to_state: str) -> PurchaseOrderApprovalVerdict:
        if from_state == to_state:
            return PurchaseOrderApprovalVerdict(
                allowed=False, reason="The order is already in that approval state."
            )
        legal = APPROVAL_STATE_TRANSITIONS.get(from_state)
        if legal is None:
            return PurchaseOrderApprovalVerdict(
                allowed=False,
                reason=f"Unknown approval state '{from_state}'.",
            )
        if to_state not in legal:
            return PurchaseOrderApprovalVerdict(
                allowed=False,
                reason=(
                    f"A '{from_state or 'unsubmitted'}' order cannot move to "
                    f"'{to_state}'."
                ),
            )
        return PurchaseOrderApprovalVerdict(allowed=True)
