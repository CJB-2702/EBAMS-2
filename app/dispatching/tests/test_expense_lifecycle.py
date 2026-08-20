"""Expense lifecycle: add/commit/complete/cancel, and its effect on the
dispatch's derived state (doc 4 §4.1)."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from datetime import timedelta

from app.dispatching.control_layer.dispatch_context import DispatchContext
from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.models.enums import ExpenseStatus
from app.dispatching.tests.base import DispatchingTestCase
from app.events.models.details.dispatching import DispatchWorkflowStatus


class ExpenseLifecycleTestCase(DispatchingTestCase):
    def _under_review_dispatch(self):
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=6)
        dispatch = DispatchFactory.create(
            domain_id=self.domain.pk, requested_for_id=self.actor.pk,
            desired_start=start, desired_end=end, asset_class_id=self.asset_class.pk,
            actor=self.actor,
        )
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit()
        ctx.take_under_review()
        return ctx

    def test_expense_requires_a_reason(self):
        ctx = self._under_review_dispatch()
        with self.assertRaises(ValueError):
            ctx.expenses.add(expense_type="contract", reason="", amount=Decimal("100"), actor=self.actor)

    def test_adding_a_live_expense_moves_dispatch_to_alternate_resolution(self):
        ctx = self._under_review_dispatch()
        ctx.expenses.add(
            expense_type="contract", reason="No suitable vehicle available",
            amount=Decimal("480.00"), counterparty_name="Halloran Haulage", actor=self.actor,
        )
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.ALTERNATE_RESOLUTION)

    def test_cancelling_the_only_expense_falls_back_to_under_review(self):
        ctx = self._under_review_dispatch()
        expense = ctx.expenses.add(
            expense_type="contract", reason="No suitable vehicle available",
            amount=Decimal("480.00"), actor=self.actor,
        )
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.ALTERNATE_RESOLUTION)

        ctx.expenses.cancel(expense_id=expense.pk, reason="found our own truck", actor=self.actor)
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.UNDER_REVIEW)

    def test_cancelled_expense_stays_visible_not_deleted(self):
        ctx = self._under_review_dispatch()
        expense = ctx.expenses.add(
            expense_type="reimbursement", reason="Used personal vehicle",
            amount=Decimal("50.00"), payee_id=self.actor.pk, actor=self.actor,
        )
        ctx.expenses.cancel(expense_id=expense.pk, reason="no longer needed", actor=self.actor)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.CANCELLED)
        self.assertEqual(expense.cancellation_reason, "no longer needed")

    def test_cancellation_requires_a_reason(self):
        ctx = self._under_review_dispatch()
        expense = ctx.expenses.add(
            expense_type="contract", reason="No suitable vehicle available",
            amount=Decimal("100.00"), actor=self.actor,
        )
        with self.assertRaises(ValueError):
            ctx.expenses.cancel(expense_id=expense.pk, reason="", actor=self.actor)

    def test_negative_amount_is_refused(self):
        ctx = self._under_review_dispatch()
        with self.assertRaises(ValueError):
            ctx.expenses.add(expense_type="contract", reason="test", amount=Decimal("-1"), actor=self.actor)

    def test_commit_then_complete_transitions(self):
        ctx = self._under_review_dispatch()
        expense = ctx.expenses.add(
            expense_type="contract", reason="No suitable vehicle available",
            amount=Decimal("200.00"), actor=self.actor,
        )
        ctx.expenses.commit(expense_id=expense.pk, actor=self.actor)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.COMMITTED)

        ctx.expenses.complete(expense_id=expense.pk, actor=self.actor)
        expense.refresh_from_db()
        self.assertEqual(expense.status, ExpenseStatus.COMPLETE)

    def test_complete_cannot_be_reached_directly_from_planned(self):
        ctx = self._under_review_dispatch()
        expense = ctx.expenses.add(
            expense_type="contract", reason="test", amount=Decimal("10.00"), actor=self.actor,
        )
        with self.assertRaises(ValueError):
            ctx.expenses.complete(expense_id=expense.pk, actor=self.actor)
