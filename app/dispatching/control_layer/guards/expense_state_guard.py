"""Guard type: StateMachine. Legal DispatchExpense.status transitions
(dispatching_starter_kit/4_dispatch_line_items.md §4)."""

from __future__ import annotations

from dataclasses import dataclass

from app.dispatching.models.enums import ExpenseStatus

EXPENSE_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    ExpenseStatus.PLANNED: frozenset({ExpenseStatus.COMMITTED, ExpenseStatus.CANCELLED}),
    ExpenseStatus.COMMITTED: frozenset({ExpenseStatus.COMPLETE, ExpenseStatus.CANCELLED}),
    ExpenseStatus.COMPLETE: frozenset(),
    ExpenseStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class TransitionVerdict:
    allowed: bool
    reason: str = ""


class ExpenseTransitionStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> TransitionVerdict:
        if from_status == to_status:
            return TransitionVerdict(allowed=False, reason="Already in that state.")
        legal = EXPENSE_STATE_TRANSITIONS.get(from_status)
        if legal is None:
            return TransitionVerdict(
                allowed=False, reason=f"'{from_status}' is not a known expense status."
            )
        if to_status not in legal:
            return TransitionVerdict(
                allowed=False, reason=f"Cannot move from '{from_status}' to '{to_status}'."
            )
        return TransitionVerdict(allowed=True)
