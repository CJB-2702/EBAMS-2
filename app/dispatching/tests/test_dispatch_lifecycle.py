"""Dispatch lifecycle: explicit verbs, IntentLockPolicy, and
DispatchStateDeriver (R8 — Planned/AlternateResolution is derived, never
assigned by hand)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from app.dispatching.control_layer.dispatch_context import DispatchContext
from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.reservation_context import ReservationContext
from app.dispatching.tests.base import DispatchingTestCase
from app.events.models.details.dispatching import DispatchWorkflowStatus


class DispatchLifecycleTestCase(DispatchingTestCase):
    def _create_dispatch(self):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=8)
        return DispatchFactory.create(
            domain_id=self.domain.pk, requested_for_id=self.actor.pk,
            desired_start=start, desired_end=end, asset_class_id=self.asset_class.pk,
            actor=self.actor,
        )

    def test_dispatch_starts_in_draft(self):
        dispatch = self._create_dispatch()
        self.assertEqual(dispatch.workflow_status, DispatchWorkflowStatus.DRAFT)

    def test_dispatch_is_its_own_event(self):
        from app.events.models.event import EventType

        dispatch = self._create_dispatch()
        self.assertEqual(dispatch.event_type, EventType.DISPATCHING)

    def test_full_queue_lifecycle(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)

        ctx.submit()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.SUBMITTED)
        self.assertIsNotNone(ctx.dispatch.submitted_at)

        ctx.take_under_review()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.UNDER_REVIEW)

        ctx.request_fixes(reason="Need more detail on cargo.")
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.FIXES_REQUESTED)

        ctx.resubmit()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.SUBMITTED)

    def test_auto_reserve_holds_only_free_assets(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk, self.asset_2.pk])
        self.assertEqual(len(ctx.struct.reservations), 2)
        for reservation in ctx.struct.reservations:
            self.assertEqual(reservation.dispatch_id, dispatch.pk)

    def test_state_becomes_planned_once_a_reservation_is_confirmed(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk])
        ctx.take_under_review()

        reservation = ctx.struct.reservations[0]
        ReservationContext(reservation.pk, self.actor).confirm()

        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

    def test_state_falls_back_to_under_review_when_reservation_cancelled_with_no_expense(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk])
        ctx.take_under_review()
        reservation = ctx.struct.reservations[0]
        ReservationContext(reservation.pk, self.actor).confirm()
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

        ReservationContext(reservation.pk, self.actor).cancel(reason="asset broke down")
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.UNDER_REVIEW)

    def test_intent_locked_once_planned(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk])
        ctx.take_under_review()
        ReservationContext(ctx.struct.reservations[0].pk, self.actor).confirm()
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

        with self.assertRaises(ValueError):
            ctx.update_intent(asset_subclass_text="changed after planning")

    def test_always_editable_fields_remain_editable_when_locked(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk])
        ctx.take_under_review()
        ReservationContext(ctx.struct.reservations[0].pk, self.actor).confirm()
        ctx.refresh()

        ctx.update_intent(description="Updated context, not a decision change.")
        self.assertEqual(ctx.dispatch.description, "Updated context, not a decision change.")

    def test_rejection_requires_a_reason(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit()
        ctx.take_under_review()
        with self.assertRaises(ValueError):
            ctx.rejection.reject(reason="", category="resource_unavailable", actor=self.actor)

    def test_rejection_freezes_intent_and_is_terminal(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit()
        ctx.take_under_review()
        ctx.rejection.reject(
            reason="No suitable asset in the fleet.", category="resource_unavailable", actor=self.actor,
        )
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.REJECTED)
        with self.assertRaises(ValueError):
            IntentLockPolicy.check_editable(dispatch=ctx.dispatch)

    def test_cancellation_carries_reason_onto_live_reservations(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.submit(candidate_asset_ids=[self.asset.pk])
        ctx.take_under_review()
        reservation = ctx.struct.reservations[0]
        ReservationContext(reservation.pk, self.actor).confirm()

        ctx.refresh()
        ctx.cancellation.cancel(reason="job no longer needed", actor=self.actor)
        reservation.refresh_from_db()
        self.assertEqual(reservation.reservation_status, "cancelled")
        self.assertEqual(reservation.cancellation_reason, "job no longer needed")

    def test_supersession_links_new_dispatch_to_the_old(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        new_dispatch = ctx.supersession.supersede(actor=self.actor)
        self.assertEqual(new_dispatch.previous_dispatch_id, dispatch.pk)
