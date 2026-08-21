"""Guard type: StateMachine. Two collaborating pieces:

DispatchTransitionStateMachine gates the EXPLICIT verbs (submit, take under
review, request fixes, resubmit, reject, complete, cancel) against
dispatching_starter_kit/2_dispatch.md §8.

DispatchStateDeriver is not a guard on a verb — it is what R8 means by
"derived, never assigned": Planned vs AlternateResolution is recomputed from
live line items after every reservation or expense change, never set by
hand. It only touches a dispatch already in the resolved region (Under
Review, Planned, or AlternateResolution); Draft/Submitted/FixesRequested/
Rejected/Completed/Cancelled are untouched by it.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.dispatching.models.enums import ExpenseStatus, ReservationStatus
from app.events.models.details.dispatching import DispatchWorkflowStatus

DISPATCH_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    DispatchWorkflowStatus.REQUESTED: frozenset(
        {
            DispatchWorkflowStatus.UNDER_REVIEW,
            DispatchWorkflowStatus.PLANNED,
            DispatchWorkflowStatus.ALTERNATE_RESOLUTION,
            DispatchWorkflowStatus.CANCELLED,
        }
    ),
    DispatchWorkflowStatus.UNDER_REVIEW: frozenset(
        {
            DispatchWorkflowStatus.FIXES_REQUESTED,
            DispatchWorkflowStatus.PLANNED,
            DispatchWorkflowStatus.ALTERNATE_RESOLUTION,
            DispatchWorkflowStatus.REJECTED,
            DispatchWorkflowStatus.CANCELLED,
        }
    ),
    DispatchWorkflowStatus.FIXES_REQUESTED: frozenset(
        {DispatchWorkflowStatus.REQUESTED, DispatchWorkflowStatus.CANCELLED}
    ),
    DispatchWorkflowStatus.PLANNED: frozenset(
        {
            DispatchWorkflowStatus.ALTERNATE_RESOLUTION,
            # Reachable only via DispatchStateDeriver — a Planned dispatch
            # that loses its only reservation with no expense to fall back on.
            DispatchWorkflowStatus.UNDER_REVIEW,
            DispatchWorkflowStatus.COMPLETED,
            DispatchWorkflowStatus.CANCELLED,
        }
    ),
    DispatchWorkflowStatus.ALTERNATE_RESOLUTION: frozenset(
        {
            DispatchWorkflowStatus.PLANNED,
            # Reachable only via DispatchStateDeriver — see PLANNED above.
            DispatchWorkflowStatus.UNDER_REVIEW,
            DispatchWorkflowStatus.COMPLETED,
            DispatchWorkflowStatus.CANCELLED,
        }
    ),
    DispatchWorkflowStatus.REJECTED: frozenset(),
    DispatchWorkflowStatus.COMPLETED: frozenset(),
    DispatchWorkflowStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class TransitionVerdict:
    allowed: bool
    reason: str = ""


class DispatchTransitionStateMachine:
    """StateMachine: is this explicit workflow_status transition legal?"""

    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> TransitionVerdict:
        if from_status == to_status:
            return TransitionVerdict(allowed=False, reason="Already in that state.")
        legal = DISPATCH_STATE_TRANSITIONS.get(from_status)
        if legal is None:
            return TransitionVerdict(
                allowed=False, reason=f"'{from_status}' is not a known dispatch status."
            )
        if to_status not in legal:
            return TransitionVerdict(
                allowed=False, reason=f"Cannot move from '{from_status}' to '{to_status}'."
            )
        return TransitionVerdict(allowed=True)


#: Reservation statuses that count as "our asset is committed" for R8.
LIVE_RESERVATION_STATUSES = frozenset(
    {
        ReservationStatus.TENTATIVE,
        ReservationStatus.CONFIRMED,
        ReservationStatus.USER_CHECKED_OUT,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    }
)

#: Expense statuses that count as "resolved another way" for R8.
LIVE_EXPENSE_STATUSES = frozenset(
    {ExpenseStatus.PLANNED, ExpenseStatus.COMMITTED, ExpenseStatus.COMPLETE}
)

_DERIVABLE_STATUSES = frozenset(
    {
        DispatchWorkflowStatus.REQUESTED,
        DispatchWorkflowStatus.UNDER_REVIEW,
        DispatchWorkflowStatus.PLANNED,
        DispatchWorkflowStatus.ALTERNATE_RESOLUTION,
    }
)


class DispatchStateDeriver:
    """StateMachine: recomputes Planned/AlternateResolution/UnderReview as a
    pure function of live line items — R8, R11, never a hand-assigned value.

    doc 4 §4.1's table is the authority here (doc 2 §12's R8 is a
    simplification of it): AlternateResolution requires a *live expense*, not
    merely the absence of a reservation. A dispatch that loses its only
    reservation with nothing else resolving the need falls back to
    UnderReview rather than being force-labelled "resolved another way" —
    the dispatcher has something to decide again, in both directions.
    """

    @classmethod
    def derive(cls, *, dispatch) -> str | None:
        """Returns the workflow_status the dispatch should move to, or None
        if no change is warranted (either it is outside the derivable region,
        or it is already correct)."""
        if dispatch.workflow_status not in _DERIVABLE_STATUSES:
            return None

        has_live_reservation = dispatch.reservations.filter(
            deleted_at__isnull=True, reservation_status__in=LIVE_RESERVATION_STATUSES
        ).exists()
        if has_live_reservation:
            target = DispatchWorkflowStatus.PLANNED
        else:
            has_live_expense = dispatch.expenses.filter(status__in=LIVE_EXPENSE_STATUSES).exists()
            target = (
                DispatchWorkflowStatus.ALTERNATE_RESOLUTION
                if has_live_expense
                else DispatchWorkflowStatus.UNDER_REVIEW
            )

        return target if target != dispatch.workflow_status else None

    @classmethod
    def apply(cls, *, dispatch_id: int, actor) -> str | None:
        """Recompute and persist, narrating the flip if one happened. Called
        after every reservation or expense change that could move the
        derived state — never in response to a manual "set status" call,
        because there is no such call for this axis."""
        from app.events.models.details.dispatching import DispatchingDetail

        dispatch = DispatchingDetail.objects.get(pk=dispatch_id, deleted_at__isnull=True)
        new_status = cls.derive(dispatch=dispatch)
        if new_status is None:
            return None

        previous = dispatch.workflow_status
        dispatch.workflow_status = new_status
        dispatch.updated_by = actor
        dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])

        from app.events.control_layer.event_context import EventContext

        EventContext(dispatch.pk, actor).add_comment(
            {
                "content": (
                    f"Dispatch state moved from '{previous}' to '{new_status}' "
                    "(derived from its live line items)."
                )
            },
            is_human_made=False,
        )
        return new_status
