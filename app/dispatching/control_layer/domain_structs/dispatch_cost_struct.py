"""Struct: "what did this job cost" — a read model over one dispatch's
expenses. Cancelled lines are excluded from the totals but never hidden
from the underlying list (R8: cancelled lines stay visible; this struct
only concerns the money question)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.dispatching.models.enums import ExpenseStatus, ExpenseType
from app.dispatching.models.line_items.dispatch_expense import DispatchExpense

_LIVE_STATUSES = frozenset({ExpenseStatus.PLANNED, ExpenseStatus.COMMITTED, ExpenseStatus.COMPLETE})


@dataclass
class DispatchCostStruct:
    dispatch_id: int
    expenses: list[DispatchExpense] = field(default_factory=list)

    @classmethod
    def load(cls, dispatch_id: int) -> "DispatchCostStruct":
        expenses = list(DispatchExpense.objects.filter(dispatch_id=dispatch_id).order_by("-created_at"))
        return cls(dispatch_id=dispatch_id, expenses=expenses)

    @property
    def live_expenses(self) -> list[DispatchExpense]:
        return [e for e in self.expenses if e.status in _LIVE_STATUSES]

    @property
    def total_committed_or_complete(self) -> Decimal:
        return sum(
            (e.amount for e in self.expenses if e.status in (ExpenseStatus.COMMITTED, ExpenseStatus.COMPLETE)),
            Decimal("0"),
        )

    @property
    def total_planned(self) -> Decimal:
        return sum((e.amount for e in self.expenses if e.status == ExpenseStatus.PLANNED), Decimal("0"))

    @property
    def total_by_type(self) -> dict[str, Decimal]:
        totals: dict[str, Decimal] = {t: Decimal("0") for t in ExpenseType.values}
        for expense in self.live_expenses:
            totals[expense.expense_type] += expense.amount
        return totals

    def to_dict(self) -> dict:
        return {
            "dispatch_id": self.dispatch_id,
            "total_planned": self.total_planned,
            "total_committed_or_complete": self.total_committed_or_complete,
            "total_by_type": self.total_by_type,
            "expense_count": len(self.expenses),
            "cancelled_count": len(self.expenses) - len(self.live_expenses),
        }
