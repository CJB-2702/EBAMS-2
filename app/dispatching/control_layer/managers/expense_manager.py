"""Manager: contract and reimbursement, one kind of record, distinguished by
type (dispatching_starter_kit/4_dispatch_line_items.md §3). Add, edit,
commit, complete — no approval workflow (§1.1). Every transition narrates
onto the dispatch timeline in the same transaction as the change, and
recomputes the dispatch's derived state, since a live/cancelled expense is
one of the two facts DispatchStateDeriver reads (R8, R11)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.expense_state_guard import (
    ExpenseTransitionStateMachine,
)
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.dispatching.models.enums import ExpenseStatus, ExpenseType
from app.dispatching.models.line_items.dispatch_expense import DispatchExpense

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ExpenseManager:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def _derive_state(self, *, actor: "AbstractUser") -> None:
        from app.dispatching.control_layer.guards.dispatch_state_guard import (
            DispatchStateDeriver,
        )

        DispatchStateDeriver.apply(dispatch_id=self.dispatch.pk, actor=actor)

    def add(
        self,
        *,
        expense_type: str,
        reason: str,
        amount: Decimal,
        counterparty_vendor_id: int | None = None,
        counterparty_name: str = "",
        payee_id: int | None = None,
        external_reference: str = "",
        notes: str = "",
        account_codes: str = "",
        actor: "AbstractUser",
    ) -> DispatchExpense:
        if expense_type not in ExpenseType.values:
            raise ValueError(f"'{expense_type}' is not a valid expense type.")
        if not (reason or "").strip():
            raise ValueError("A reason is required — why this was needed instead of our own assets.")
        if amount < 0:
            raise ValueError("Amount cannot be negative.")

        with transaction.atomic():
            expense = DispatchExpense.objects.create(
                dispatch=self.dispatch,
                expense_type=expense_type,
                status=ExpenseStatus.PLANNED,
                reason=reason,
                amount=amount,
                counterparty_vendor_id=counterparty_vendor_id,
                counterparty_name=counterparty_name,
                payee_id=payee_id,
                external_reference=external_reference,
                notes=notes,
                account_codes=account_codes,
                created_by=actor,
                updated_by=actor,
            )

        counterparty = counterparty_name or (
            expense.counterparty_vendor.name if expense.counterparty_vendor_id else "unspecified"
        )
        self._ctx._narrate(
            DispatchNarrator.expense_added(expense_type=expense_type, counterparty=counterparty, amount=amount)
        )
        self._derive_state(actor=actor)
        self._ctx.refresh()
        return expense

    def update_fields(self, *, expense_id: int, actor: "AbstractUser", **fields) -> DispatchExpense:
        expense = DispatchExpense.objects.get(pk=expense_id, dispatch_id=self.dispatch.pk)
        editable = {
            "reason", "amount", "counterparty_vendor_id", "counterparty_name", "payee_id",
            "external_reference", "notes", "account_codes",
        }
        update_fields: list[str] = []
        for field_name, value in fields.items():
            if field_name not in editable:
                continue
            setattr(expense, field_name, value)
            update_fields.append(field_name.removesuffix("_id"))
        if update_fields:
            expense.updated_by = actor
            expense.save()
        self._ctx.refresh()
        return expense

    def _transition(self, *, expense: DispatchExpense, to_status: str) -> None:
        verdict = ExpenseTransitionStateMachine.check(from_status=expense.status, to_status=to_status)
        if not verdict.allowed:
            raise ValueError(verdict.reason)

    def commit(self, *, expense_id: int, actor: "AbstractUser") -> DispatchExpense:
        expense = DispatchExpense.objects.get(pk=expense_id, dispatch_id=self.dispatch.pk)
        self._transition(expense=expense, to_status=ExpenseStatus.COMMITTED)
        previous = expense.status
        with transaction.atomic():
            expense.status = ExpenseStatus.COMMITTED
            expense.updated_by = actor
            expense.save(update_fields=["status", "updated_by", "updated_at"])
        self._ctx._narrate(
            DispatchNarrator.expense_status_changed(
                expense_id=expense.pk, previous=previous, new=ExpenseStatus.COMMITTED
            )
        )
        self._derive_state(actor=actor)
        self._ctx.refresh()
        return expense

    def complete(self, *, expense_id: int, actor: "AbstractUser") -> DispatchExpense:
        expense = DispatchExpense.objects.get(pk=expense_id, dispatch_id=self.dispatch.pk)
        self._transition(expense=expense, to_status=ExpenseStatus.COMPLETE)
        previous = expense.status
        with transaction.atomic():
            expense.status = ExpenseStatus.COMPLETE
            expense.updated_by = actor
            expense.save(update_fields=["status", "updated_by", "updated_at"])
        self._ctx._narrate(
            DispatchNarrator.expense_status_changed(
                expense_id=expense.pk, previous=previous, new=ExpenseStatus.COMPLETE
            )
        )
        self._derive_state(actor=actor)
        self._ctx.refresh()
        return expense

    def cancel(self, *, expense_id: int, reason: str, actor: "AbstractUser") -> DispatchExpense:
        """Cancellation is a status, never a deletion — the line stays
        visible (R7, R8)."""
        if not (reason or "").strip():
            raise ValueError("A cancellation reason is required.")
        expense = DispatchExpense.objects.get(pk=expense_id, dispatch_id=self.dispatch.pk)
        self._transition(expense=expense, to_status=ExpenseStatus.CANCELLED)

        from django.utils import timezone

        with transaction.atomic():
            expense.status = ExpenseStatus.CANCELLED
            expense.cancellation_reason = reason
            expense.cancelled_by = actor
            expense.cancelled_at = timezone.now()
            expense.updated_by = actor
            expense.save()
        self._ctx._narrate(DispatchNarrator.expense_cancelled(expense_id=expense.pk, reason=reason))
        self._derive_state(actor=actor)
        self._ctx.refresh()
        return expense
