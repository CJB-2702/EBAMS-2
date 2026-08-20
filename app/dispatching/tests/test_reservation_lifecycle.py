"""Integration: the reservation lifecycle works end to end with no dispatch
in the database (build_phase_2_control_layer.md "Done when")."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.control_layer.reservation_context import ReservationContext
from app.dispatching.models.enums import ReservationStatus, ReservationType
from app.dispatching.models.reservations.reservation_update import ReservationUpdate
from app.dispatching.tests.base import DispatchingTestCase
from app.events.models.event import EventType


class StandaloneReservationLifecycleTestCase(DispatchingTestCase):
    def _create(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=8)
        return ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=start, scheduled_end=end,
            actor=self.actor,
        )

    def test_created_reservation_has_no_dispatch(self):
        reservation = self._create()
        self.assertIsNone(reservation.dispatch_id)
        self.assertEqual(reservation.reservation_status, ReservationStatus.TENTATIVE)

    def test_created_reservation_is_its_own_event(self):
        reservation = self._create()
        self.assertEqual(reservation.event_type, EventType.RESERVATION)
        self.assertEqual(reservation.thread_type, "event")

    def test_full_confirm_checkout_return_cycle(self):
        reservation = self._create()
        ctx = ReservationContext(reservation.pk, self.actor)

        ctx.confirm()
        self.assertEqual(ctx.reservation.reservation_status, ReservationStatus.CONFIRMED)

        ctx.checkout.dispatcher_verify_checkout(condition="good", notes="pre-trip ok")
        self.assertEqual(ctx.reservation.reservation_status, ReservationStatus.CHECKED_OUT)
        self.assertIsNotNone(ctx.reservation.physical_checkout_at)

        ctx.checkout.dispatcher_verify_return(condition="fair", notes="minor scuff")
        self.assertEqual(ctx.reservation.reservation_status, ReservationStatus.RETURNED)
        self.assertIsNotNone(ctx.reservation.physical_checkin_at)

        self.assertGreaterEqual(
            ReservationUpdate.objects.filter(reservation=reservation).count(), 2
        )

    def test_dual_handover_tracks_are_independent(self):
        reservation = self._create()
        ctx = ReservationContext(reservation.pk, self.actor)
        ctx.confirm()

        self_service_ctx = ReservationContext(reservation.pk, self.actor)
        self_service_ctx.checkout.user_checkout(condition="good", notes="looks fine to me")

        dispatcher_ctx = ReservationContext(reservation.pk, self.other_user)
        dispatcher_ctx.checkout.dispatcher_verify_checkout(condition="fair", notes="found a scratch")

        reservation.refresh_from_db()
        self.assertEqual(reservation.user_reported_condition_out, "good")
        self.assertEqual(reservation.condition_out, "fair")
        self.assertNotEqual(reservation.user_reported_condition_out, reservation.condition_out)

    def test_verifier_cannot_be_the_self_service_actor(self):
        reservation = self._create()
        ctx = ReservationContext(reservation.pk, self.actor)
        ctx.confirm()

        self_service_ctx = ReservationContext(reservation.pk, self.actor)
        self_service_ctx.checkout.user_checkout()

        same_person_ctx = ReservationContext(reservation.pk, self.actor)
        with self.assertRaises(ValueError):
            same_person_ctx.checkout.dispatcher_verify_checkout()

    def test_cancel_requires_a_reason(self):
        reservation = self._create()
        ctx = ReservationContext(reservation.pk, self.actor)
        with self.assertRaises(ValueError):
            ctx.cancel(reason="")

    def test_cancel_records_reason_and_actor(self):
        reservation = self._create()
        ctx = ReservationContext(reservation.pk, self.actor)
        ctx.cancel(reason="vehicle failed pre-trip inspection")
        self.assertEqual(ctx.reservation.reservation_status, ReservationStatus.CANCELLED)
        self.assertEqual(ctx.reservation.cancellation_reason, "vehicle failed pre-trip inspection")
        self.assertEqual(ctx.reservation.cancelled_by_id, self.actor.pk)
