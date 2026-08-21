"""Dispatch lifecycle: explicit verbs, IntentLockPolicy, and
DispatchStateDeriver (R8 — Planned/AlternateResolution is derived, never
assigned by hand)."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from app.dispatching.control_layer.dispatch_context import DispatchContext
from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.managers.reservation_promotion_manager import ReservationPromotionManager
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

    def _attach_reservation(self, dispatch_pk, asset):
        res = ReservationFactory.create(
            asset_id=asset.pk,
            domain_id=self.domain.pk,
            reservation_type="work",
            accountable_person_id=self.actor.pk,
            scheduled_start=timezone.now() + timedelta(days=2),
            scheduled_end=timezone.now() + timedelta(days=2, hours=8),
            actor=self.actor,
        )
        ReservationPromotionManager.promote(
            reservation_id=res.pk, dispatch_id=dispatch_pk, actor=self.actor
        )
        return res

    def test_dispatch_starts_in_requested(self):
        dispatch = self._create_dispatch()
        self.assertEqual(dispatch.workflow_status, DispatchWorkflowStatus.REQUESTED)

    def test_dispatch_is_its_own_event(self):
        from app.events.models.event import EventType

        dispatch = self._create_dispatch()
        self.assertEqual(dispatch.event_type, EventType.DISPATCHING)

    def test_full_queue_lifecycle(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)

        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.REQUESTED)
        self.assertIsNotNone(ctx.dispatch.submitted_at)

        ctx.take_under_review()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.UNDER_REVIEW)

        ctx.request_fixes(reason="Need more detail on cargo.")
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.FIXES_REQUESTED)

        ctx.resubmit()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.REQUESTED)

    def test_reservation_promotion_links_booking(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        self.assertEqual(len(ctx.struct.reservations), 1)
        self.assertEqual(ctx.struct.reservations[0].dispatch_id, dispatch.pk)

    def test_state_becomes_planned_once_a_reservation_is_confirmed(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()

        ReservationContext(res.pk, self.actor).confirm()

        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

    def test_state_falls_back_to_under_review_when_reservation_cancelled_with_no_expense(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        ReservationContext(res.pk, self.actor).confirm()
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

        ReservationContext(res.pk, self.actor).cancel(reason="asset broke down")
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.UNDER_REVIEW)

    def test_intent_locked_once_planned(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        ReservationContext(res.pk, self.actor).confirm()
        ctx.refresh()
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.PLANNED)

        with self.assertRaises(ValueError):
            ctx.update_intent(asset_subclass_text="changed after planning")

    def test_always_editable_fields_remain_editable_when_locked(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        ReservationContext(res.pk, self.actor).confirm()
        ctx.refresh()

        ctx.update_intent(description="Updated context, not a decision change.")
        self.assertEqual(ctx.dispatch.description, "Updated context, not a decision change.")

    def test_rejection_requires_a_reason(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        with self.assertRaises(ValueError):
            ctx.rejection.reject(reason="", category="resource_unavailable", actor=self.actor)

    def test_rejection_freezes_intent_and_is_terminal(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        ctx.rejection.reject(
            reason="No suitable asset in the fleet.", category="resource_unavailable", actor=self.actor,
        )
        self.assertEqual(ctx.dispatch.workflow_status, DispatchWorkflowStatus.REJECTED)
        with self.assertRaises(ValueError):
            IntentLockPolicy.check_editable(dispatch=ctx.dispatch)

    def test_cancellation_carries_reason_onto_live_reservations(self):
        dispatch = self._create_dispatch()
        res = self._attach_reservation(dispatch.pk, self.asset)
        ctx = DispatchContext(dispatch.pk, self.actor)
        ctx.take_under_review()
        ReservationContext(res.pk, self.actor).confirm()

        ctx.refresh()
        ctx.cancellation.cancel(reason="job no longer needed", actor=self.actor)
        res.refresh_from_db()
        self.assertEqual(res.reservation_status, "cancelled")
        self.assertEqual(res.cancellation_reason, "job no longer needed")

    def test_supersession_links_new_dispatch_to_the_old(self):
        dispatch = self._create_dispatch()
        ctx = DispatchContext(dispatch.pk, self.actor)
        new_dispatch = ctx.supersession.supersede(actor=self.actor)
        self.assertEqual(new_dispatch.previous_dispatch_id, dispatch.pk)

    def test_personnel_search_and_crew_htmx(self):
        from app.administration.auth_session import SESSION_KEY_DOMAIN_IDS, SESSION_KEY_PERMISSION_CODENAMES
        from app.administration.models import UserDomain
        from django.contrib.auth.models import Permission
        from django.urls import reverse

        p1 = Permission.objects.get(codename="dispatch_raise")
        p2 = Permission.objects.get(codename="dispatch_plan")
        self.actor.user_permissions.add(p1, p2)
        self.actor.refresh_from_db()
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(self.actor, attr):
                delattr(self.actor, attr)

        UserDomain.objects.create(user=self.actor, domain=self.domain, is_active=True)

        self.client.force_login(self.actor)
        session = self.client.session
        session[SESSION_KEY_DOMAIN_IDS] = [self.domain.pk]
        session[SESSION_KEY_PERMISSION_CODENAMES] = sorted(self.actor.get_all_permissions())
        session.save()

        dispatch = self._create_dispatch()

        # Test search GET endpoint
        url_search = reverse("dispatching_dispatch_personnel_search", kwargs={"pk": dispatch.pk}) + f"?user_name={self.actor.username}"
        res_search = self.client.get(url_search, HTTP_HX_REQUEST="true")
        print("SEARCH CONTENT:", res_search.content.decode("utf-8"))
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, self.actor.username)

        # Test crew add action via HTMX
        url_crew = reverse("dispatching_dispatch_crew_action", kwargs={"pk": dispatch.pk})
        res_add = self.client.post(
            url_crew,
            {"action": "add", "user_id": self.actor.pk, "role": "driver"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(res_add.status_code, 200)
        self.assertContains(res_add, "Personnel Selection / Crew Roster")
