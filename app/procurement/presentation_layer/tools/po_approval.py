"""The PO approval axis, as the presentation layer needs to read it.

Phase 0 adds `PurchaseOrder.approval_state` and the three verbs
(`submit_for_approval`, `approve_order`, `deny_order`) on `PurchaseOrderContext`.
This module is the single seam Phase 2's pages read that axis through, so the
sector's templates and entrypoints do not each grow their own `getattr` dance
while the two phases are in flight.

WHEN PHASE 0 MERGES: delete `_FallbackApprovalState` and the `getattr` in
`state_of`, import the real enum directly, and drop `run_verb`'s AttributeError
branch. Nothing else in the sector needs to change — that is the point of
routing through one file.

The axis (Phase 0 §4):

    Unsubmitted -> Pending Approval -> Approved
         |                 |
         +----> Denied / Cancelled (from either non-terminal state)

`Approved` is NOT revocable through this axis; an approved order is cancelled
through `status`.
"""

from __future__ import annotations

from app.procurement.control_layer.errors import ProcurementValidationError


class _FallbackApprovalState:
    """Mirror of Phase 0's enum, used only until its migration lands."""

    UNSUBMITTED = "unsubmitted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    DENIED = "denied"
    CANCELLED = "cancelled"


try:  # pragma: no cover - depends on which phase has merged
    from app.procurement.models import (  # type: ignore[attr-defined]
        PurchaseOrderApprovalState as ApprovalState,
    )
except ImportError:
    ApprovalState = _FallbackApprovalState  # type: ignore[assignment]


LABELS = {
    _FallbackApprovalState.UNSUBMITTED: "Unsubmitted",
    _FallbackApprovalState.PENDING_APPROVAL: "Pending Approval",
    _FallbackApprovalState.APPROVED: "Approved",
    _FallbackApprovalState.DENIED: "Denied",
    _FallbackApprovalState.CANCELLED: "Cancelled",
}

#: Bulma modifier per state, for the hero badge and the list's filter chips.
TAG_CLASSES = {
    _FallbackApprovalState.UNSUBMITTED: "is-light",
    _FallbackApprovalState.PENDING_APPROVAL: "is-warning",
    _FallbackApprovalState.APPROVED: "is-success",
    _FallbackApprovalState.DENIED: "is-danger",
    _FallbackApprovalState.CANCELLED: "is-dark",
}

#: Ordered for the index page's filter select.
CHOICES = tuple(LABELS.items())

_NON_TERMINAL = frozenset(
    {
        _FallbackApprovalState.UNSUBMITTED,
        _FallbackApprovalState.PENDING_APPROVAL,
    }
)


def state_of(purchase_order) -> str:
    """The PO's approval state. A blank column reads as Unsubmitted (D65's
    blank-is-a-real-value precedent), so an order predating the axis is
    correctly "nobody has submitted this yet" rather than an empty badge."""
    return (
        getattr(purchase_order, "approval_state", "") or _FallbackApprovalState.UNSUBMITTED
    )


def label_of(purchase_order) -> str:
    return LABELS.get(state_of(purchase_order), "Unsubmitted")


def tag_class_of(purchase_order) -> str:
    return TAG_CLASSES.get(state_of(purchase_order), "is-light")


def can_submit_for_approval(purchase_order) -> bool:
    return state_of(purchase_order) == _FallbackApprovalState.UNSUBMITTED


def can_decide(purchase_order) -> bool:
    """Approve and Deny are both reachable only from Pending Approval."""
    return state_of(purchase_order) == _FallbackApprovalState.PENDING_APPROVAL


def can_deny(purchase_order) -> bool:
    """Deny is reachable directly from either non-terminal state (Phase 0 §4)."""
    return state_of(purchase_order) in _NON_TERMINAL


def can_place(purchase_order) -> bool:
    """THE GATE. `place` refuses unless the order has been approved."""
    return state_of(purchase_order) == _FallbackApprovalState.APPROVED


def is_self_approval(purchase_order, actor) -> bool:
    """Legal, and recorded. One person may hold both `buy` and
    `purchase_approve` and approve their own order — small organizations run
    this way. The narrator posts a machine comment; the UI never blocks it."""
    creator_id = getattr(purchase_order, "created_by_id", None)
    return creator_id is not None and creator_id == getattr(actor, "pk", None)


def run_verb(context, verb: str, *, actor):
    """Call one of Phase 0's approval verbs on a `PurchaseOrderContext`.

    Raises a plain validation error, not an AttributeError, when Phase 0's
    control-layer follow-through has not merged yet — an operator hitting the
    button deserves to be told which build step is missing.
    """
    method = getattr(context, verb, None)
    if method is None:
        raise ProcurementValidationError(
            [
                f"The approval action '{verb}' is not available yet — it lands with "
                f"Phase 0's control-layer follow-through on PurchaseOrderContext."
            ]
        )
    return method(actor=actor)
