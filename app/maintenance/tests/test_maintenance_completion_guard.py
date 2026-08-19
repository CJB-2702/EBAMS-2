"""R4 completion truth table (MaintenanceCompletionPolicy), including the
billable-hours floor: MaintenanceDetail.actual_billable_hours must be >= the
sum of the individual Action.billable_hours values before an event may
complete. A manual override running ahead of the calculated sum is fine —
only falling short blocks completion.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.maintenance.control_layer.guards.maintenance_completion_guard import (
    MaintenanceCompletionPolicy,
)
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.models.action import Action, ActionStatus

User = get_user_model()


class MaintenanceCompletionGuardTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="completion_tester", email="completion_tester@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Completion Domain", slug="completion-domain",
            created_by=cls.user, updated_by=cls.user,
        )

    def _make_event(self, actual_billable_hours=None):
        return MaintenanceDetail.objects.create(
            domain=self.domain,
            title="Test event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            assigned_user=self.user,
            actual_billable_hours=actual_billable_hours,
            created_by=self.user, updated_by=self.user,
        )

    def _make_action(self, event, *, billable_hours=None, status=ActionStatus.COMPLETE):
        return Action.objects.create(
            event_detail=event,
            action_name="Step",
            sequence_order=1,
            status=status,
            billable_hours=billable_hours,
            created_by=self.user, updated_by=self.user,
        )

    def test_allowed_when_no_actions_have_billable_hours_and_none_recorded(self):
        event = self._make_event(actual_billable_hours=None)
        self._make_action(event, billable_hours=None)
        ctx = MaintenanceContext(event.pk)
        verdict = ctx.completion_verdict()
        self.assertTrue(verdict.allowed, verdict.reasons)

    def test_blocked_when_actual_is_short_of_the_calculated_sum(self):
        event = self._make_event(actual_billable_hours=3.0)
        self._make_action(event, billable_hours=2.0)
        self._make_action(event, billable_hours=2.5)
        ctx = MaintenanceContext(event.pk)
        verdict = ctx.completion_verdict()
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("billable hours" in r for r in verdict.reasons))

    def test_allowed_when_actual_meets_the_calculated_sum(self):
        event = self._make_event(actual_billable_hours=4.5)
        self._make_action(event, billable_hours=2.0)
        self._make_action(event, billable_hours=2.5)
        ctx = MaintenanceContext(event.pk)
        verdict = ctx.completion_verdict()
        self.assertTrue(verdict.allowed, verdict.reasons)

    def test_allowed_when_actual_exceeds_the_calculated_sum(self):
        # A manual override running ahead of the calculated sum is fine —
        # only falling short blocks completion.
        event = self._make_event(actual_billable_hours=10.0)
        self._make_action(event, billable_hours=2.0)
        ctx = MaintenanceContext(event.pk)
        verdict = ctx.completion_verdict()
        self.assertTrue(verdict.allowed, verdict.reasons)

    def test_blocked_when_actions_have_hours_but_nothing_recorded_at_event_level(self):
        event = self._make_event(actual_billable_hours=None)
        self._make_action(event, billable_hours=1.0)
        ctx = MaintenanceContext(event.pk)
        verdict = ctx.completion_verdict()
        self.assertFalse(verdict.allowed)

    def test_complete_raises_when_billable_hours_short(self):
        event = self._make_event(actual_billable_hours=1.0)
        self._make_action(event, billable_hours=5.0)
        ctx = MaintenanceContext(event.pk)
        with self.assertRaises(ValueError):
            ctx.complete(actor=self.user)

    def test_complete_succeeds_once_billable_hours_are_sufficient(self):
        event = self._make_event(actual_billable_hours=5.0)
        self._make_action(event, billable_hours=5.0)
        ctx = MaintenanceContext(event.pk)
        completed = ctx.complete(actor=self.user)
        self.assertEqual(completed.status, "complete")


class FailedActionsAreTerminalTests(MaintenanceCompletionGuardTestCase):
    """A failed step is settled work, not outstanding work.

    This guard previously counted only Complete and Skipped as terminal while
    ActionContext.TERMINAL_STATUSES already included Failed. The disagreement
    meant a genuinely failed step could never be cleared: no verb moves an
    action out of Failed except an explicit reopen, so the event was stuck
    forever unless the technician lied about the outcome.
    """

    def test_an_event_whose_only_action_failed_can_still_complete(self):
        event = self._make_event()
        self._make_action(event, status=ActionStatus.FAILED)
        verdict = MaintenanceCompletionPolicy.check(
            struct=MaintenanceContext(event.pk).struct
        )
        self.assertTrue(verdict.allowed, verdict.reasons)

    def test_a_mix_of_complete_failed_and_skipped_can_complete(self):
        event = self._make_event()
        for order, status in enumerate(
            (ActionStatus.COMPLETE, ActionStatus.FAILED, ActionStatus.SKIPPED), start=1
        ):
            Action.objects.create(
                event_detail=event, action_name=f"Step {order}",
                sequence_order=order, status=status,
                created_by=self.user, updated_by=self.user,
            )
        verdict = MaintenanceCompletionPolicy.check(
            struct=MaintenanceContext(event.pk).struct
        )
        self.assertTrue(verdict.allowed, verdict.reasons)

    def test_blocked_is_still_not_terminal(self):
        # Blocked is the one non-terminal interruption: it is explicitly
        # expected to come back, so it must keep holding completion open.
        event = self._make_event()
        self._make_action(event, status=ActionStatus.BLOCKED)
        verdict = MaintenanceCompletionPolicy.check(
            struct=MaintenanceContext(event.pk).struct
        )
        self.assertFalse(verdict.allowed)

    def test_in_progress_is_still_not_terminal(self):
        event = self._make_event()
        self._make_action(event, status=ActionStatus.IN_PROGRESS)
        verdict = MaintenanceCompletionPolicy.check(
            struct=MaintenanceContext(event.pk).struct
        )
        self.assertFalse(verdict.allowed)
