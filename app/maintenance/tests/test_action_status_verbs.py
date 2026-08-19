"""ActionContext's two new lifecycle verbs, added for the work portal port.

`mark_blocked` and `reopen` are the halves of the legacy work portal's
"Blocked" / "Resume" / "Change" buttons. The distinctions worth pinning down:

  * blocked is NOT terminal — nobody finished anything, so no end_time and no
    completed_by, and the step must still be able to leave the state;
  * reopen clears end_time, because a step that is back in progress is not a
    step that ended;
  * both are refusals-by-no-op from states the transition does not apply to,
    matching the rest of ActionContext.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from datetime import timedelta

from django.utils import timezone

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.maintenance.control_layer.action_context import ActionContext
from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.blocker import BlockerReason

User = get_user_model()


class ActionStatusVerbTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="verb_tester", email="verb_tester@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Verb Domain", slug="verb-domain",
            created_by=cls.user, updated_by=cls.user,
        )
        cls.event = MaintenanceDetail.objects.create(
            domain=cls.domain,
            title="Verb event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            created_by=cls.user, updated_by=cls.user,
        )

    def _action(self, status=ActionStatus.IN_PROGRESS, **kwargs):
        return Action.objects.create(
            event_detail=self.event,
            action_name="Step",
            sequence_order=1,
            status=status,
            created_by=self.user, updated_by=self.user,
            **kwargs,
        )

    # ── mark_blocked ────────────────────────────────────────────────── #

    def test_blocking_an_in_progress_step_records_the_reason(self):
        action = self._action()
        ActionContext(action.pk).mark_blocked(actor=self.user, notes="Waiting on parts")
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.BLOCKED)
        self.assertEqual(action.completion_notes, "Waiting on parts")

    def test_blocking_does_not_end_the_step(self):
        action = self._action()
        ActionContext(action.pk).mark_blocked(actor=self.user, notes="Waiting on parts")
        action.refresh_from_db()
        self.assertIsNone(action.end_time)
        self.assertIsNone(action.completed_by)

    def test_blocking_a_completed_step_is_refused(self):
        action = self._action(status=ActionStatus.COMPLETE)
        ActionContext(action.pk).mark_blocked(actor=self.user, notes="too late")
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.COMPLETE)

    # ── reopen ──────────────────────────────────────────────────────── #

    def test_reopening_a_blocked_step_puts_it_back_in_progress(self):
        action = self._action(status=ActionStatus.BLOCKED)
        ActionContext(action.pk).reopen(actor=self.user, notes="Parts arrived")
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.IN_PROGRESS)

    def test_reopening_clears_the_end_time(self):
        action = self._action(status=ActionStatus.COMPLETE, end_time=timezone.now())
        ActionContext(action.pk).reopen(actor=self.user, notes="Marked complete in error")
        action.refresh_from_db()
        self.assertIsNone(action.end_time)

    def test_reopening_a_skipped_step_backfills_a_start_time(self):
        # A skipped step was never started, so it has no start_time to keep.
        action = self._action(status=ActionStatus.SKIPPED)
        self.assertIsNone(action.start_time)
        ActionContext(action.pk).reopen(actor=self.user, notes="Doing it after all")
        action.refresh_from_db()
        self.assertIsNotNone(action.start_time)

    def test_reopening_preserves_an_existing_start_time(self):
        started = timezone.now()
        action = self._action(status=ActionStatus.FAILED, start_time=started)
        ActionContext(action.pk).reopen(actor=self.user, notes="Retrying")
        action.refresh_from_db()
        self.assertEqual(action.start_time, started)

    def test_reopening_a_not_started_step_is_refused(self):
        action = self._action(status=ActionStatus.NOT_STARTED)
        ActionContext(action.pk).reopen(actor=self.user, notes="nothing to reopen")
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.NOT_STARTED)

    # ── mark_skipped now accepts Blocked ────────────────────────────── #

    def test_a_blocked_step_can_be_skipped(self):
        # Legacy let a technician abandon a step they had blocked; without
        # this, a blocked step could only ever be resumed.
        action = self._action(status=ActionStatus.BLOCKED)
        ActionContext(action.pk).mark_skipped(actor=self.user, notes="Not needed after all")
        action.refresh_from_db()
        self.assertEqual(action.status, ActionStatus.SKIPPED)


class InterruptionResolutionNotesTestCase(TestCase):
    """Resolving a blocker or closing a limitation requires a stated reason.

    Both records open with a cause ("parts not available", "cannot tow").
    Closing one silently leaves a half-record: the log says work stopped and
    then says nothing about why it started again. The refusal lives in the
    manager, not just the form, so a plain POST cannot skip it.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="resolution_tester", email="resolution_tester@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Resolution Domain", slug="resolution-domain",
            created_by=cls.user, updated_by=cls.user,
        )

    def _context(self):
        from app.maintenance.control_layer.maintenance_context import MaintenanceContext

        event = MaintenanceDetail.objects.create(
            domain=self.domain,
            title="Resolution event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            created_by=self.user, updated_by=self.user,
        )
        return MaintenanceContext(event.pk)

    def test_resolving_a_blocker_records_the_reason(self):
        ctx = self._context()
        blocker = ctx.blocker_manager.add_blocker(
            reason=BlockerReason.PARTS_NOT_AVAILABLE, actor=self.user
        )
        ctx.blocker_manager.end_blocker(
            blocker_id=blocker.pk, resolution_notes="Parts arrived", actor=self.user
        )
        blocker.refresh_from_db()
        self.assertIsNotNone(blocker.end_date)
        self.assertEqual(blocker.resolution_notes, "Parts arrived")

    def test_resolving_a_blocker_without_a_reason_is_refused(self):
        ctx = self._context()
        blocker = ctx.blocker_manager.add_blocker(
            reason=BlockerReason.PARTS_NOT_AVAILABLE, actor=self.user
        )
        with self.assertRaises(ValueError):
            ctx.blocker_manager.end_blocker(
                blocker_id=blocker.pk, resolution_notes="   ", actor=self.user
            )
        blocker.refresh_from_db()
        self.assertIsNone(blocker.end_date)

    def test_closing_a_limitation_records_the_reason(self):
        ctx = self._context()
        record = ctx.limitation_manager.create_record(
            status="Non Capable", limitation_description="Cannot tow", actor=self.user
        )
        ctx.limitation_manager.close_record(
            record_id=record.pk, resolution_notes="Hitch replaced", actor=self.user
        )
        record.refresh_from_db()
        self.assertIsNotNone(record.end_time)
        self.assertEqual(record.resolution_notes, "Hitch replaced")

    def test_closing_a_limitation_without_a_reason_is_refused(self):
        ctx = self._context()
        record = ctx.limitation_manager.create_record(
            status="Non Capable", limitation_description="Cannot tow", actor=self.user
        )
        with self.assertRaises(ValueError):
            ctx.limitation_manager.close_record(
                record_id=record.pk, resolution_notes="", actor=self.user
            )
        record.refresh_from_db()
        self.assertIsNone(record.end_time)


class BlockerScopeTestCase(TestCase):
    """A blocked STEP and a blocked EVENT are different records.

    Blocking one action means the technician moves on to the next step.
    Opening a MaintenanceBlocker means the whole job has stopped. Merging
    them would turn every "waiting on a torque wrench" into a reportable
    work stoppage, so the separation is pinned here.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="scope_tester", email="scope_tester@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Scope Domain", slug="scope-domain",
            created_by=cls.user, updated_by=cls.user,
        )

    def _event(self):
        from app.events.models.event import EventStatus

        return MaintenanceDetail.objects.create(
            domain=self.domain,
            title="Scope event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            status=EventStatus.IN_PROGRESS,
            created_by=self.user, updated_by=self.user,
        )

    def test_blocking_a_step_does_not_create_a_maintenance_blocker(self):
        from app.maintenance.models.blocker import MaintenanceBlocker

        event = self._event()
        action = Action.objects.create(
            event_detail=event, action_name="Step", sequence_order=1,
            status=ActionStatus.IN_PROGRESS,
            created_by=self.user, updated_by=self.user,
        )
        ActionContext(action.pk).mark_blocked(actor=self.user, notes="No torque wrench")
        self.assertFalse(MaintenanceBlocker.objects.filter(maintenance_detail=event).exists())

    def test_blocking_a_step_does_not_block_the_event(self):
        from app.events.models.event import EventStatus

        event = self._event()
        action = Action.objects.create(
            event_detail=event, action_name="Step", sequence_order=1,
            status=ActionStatus.IN_PROGRESS,
            created_by=self.user, updated_by=self.user,
        )
        ActionContext(action.pk).mark_blocked(actor=self.user, notes="No torque wrench")
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.IN_PROGRESS)

    def test_opening_a_maintenance_blocker_does_block_the_event(self):
        from app.events.models.event import EventStatus
        from app.maintenance.control_layer.maintenance_context import MaintenanceContext
        from app.maintenance.models.blocker import BlockerReason

        event = self._event()
        MaintenanceContext(event.pk).blocker_manager.add_blocker(
            reason=BlockerReason.SAFETY_CONCERNS, actor=self.user
        )
        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.BLOCKED)


class BlockerCloseOutTestCase(TestCase):
    """The close-out form is where the facts get corrected.

    At open, billable_hours_lost is a guess and the start time is whenever
    somebody got round to logging it. Closing is when both are actually
    known, so both are writable on the way out (legacy's "End Blocked
    Status" form).
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="closeout_tester", email="closeout_tester@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Closeout Domain", slug="closeout-domain",
            created_by=cls.user, updated_by=cls.user,
        )

    def _blocker(self, **kwargs):
        from app.maintenance.control_layer.maintenance_context import MaintenanceContext
        from app.maintenance.models.blocker import BlockerReason

        event = MaintenanceDetail.objects.create(
            domain=self.domain,
            title="Closeout event",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            created_by=self.user, updated_by=self.user,
        )
        ctx = MaintenanceContext(event.pk)
        blocker = ctx.blocker_manager.add_blocker(
            reason=BlockerReason.PARTS_NOT_AVAILABLE, actor=self.user, **kwargs
        )
        return ctx, blocker

    def test_hours_lost_supplied_at_close_overwrites_the_estimate(self):
        ctx, blocker = self._blocker(billable_hours_lost=1.0)
        ctx.blocker_manager.end_blocker(
            blocker_id=blocker.pk,
            resolution_notes="Parts arrived",
            billable_hours_lost=4.75,
            actor=self.user,
        )
        blocker.refresh_from_db()
        self.assertEqual(blocker.billable_hours_lost, 4.75)

    def test_hours_lost_omitted_at_close_keeps_the_estimate(self):
        ctx, blocker = self._blocker(billable_hours_lost=1.0)
        ctx.blocker_manager.end_blocker(
            blocker_id=blocker.pk, resolution_notes="Parts arrived", actor=self.user
        )
        blocker.refresh_from_db()
        self.assertEqual(blocker.billable_hours_lost, 1.0)

    def test_the_start_time_can_be_corrected_on_the_way_out(self):
        ctx, blocker = self._blocker()
        earlier = timezone.now() - timedelta(hours=6)
        ctx.blocker_manager.end_blocker(
            blocker_id=blocker.pk,
            resolution_notes="Parts arrived",
            start_date=earlier,
            actor=self.user,
        )
        blocker.refresh_from_db()
        self.assertEqual(blocker.start_date, earlier)

    def test_a_blocker_cannot_end_before_it_started(self):
        ctx, blocker = self._blocker()
        with self.assertRaises(ValueError):
            ctx.blocker_manager.end_blocker(
                blocker_id=blocker.pk,
                resolution_notes="Parts arrived",
                end_date=timezone.now() - timedelta(days=1),
                actor=self.user,
            )
        blocker.refresh_from_db()
        self.assertIsNone(blocker.end_date)

    def test_an_invalid_reason_is_refused(self):
        from app.maintenance.control_layer.maintenance_context import MaintenanceContext

        event = MaintenanceDetail.objects.create(
            domain=self.domain, title="Bad reason event",
            event_type=EventType.MAINTENANCE, event_start=timezone.now(),
            maintenance_type="scheduled",
            created_by=self.user, updated_by=self.user,
        )
        with self.assertRaises(ValueError):
            MaintenanceContext(event.pk).blocker_manager.add_blocker(
                reason="Ran out of coffee", actor=self.user
            )
