"""Guards named in build_phase_2_control_layer.md §4: DoubleBookingPolicy,
AccountablePersonPolicy, VerifierDistinctPolicy, ReservationDeletionPolicy,
plus ReservationTransitionStateMachine."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.control_layer.guards.accountable_person_guard import (
    AccountablePersonPolicy,
)
from app.dispatching.control_layer.guards.double_booking_guard import DoubleBookingPolicy
from app.dispatching.control_layer.guards.reservation_deletion_guard import (
    ReservationDeletionPolicy,
)
from app.dispatching.control_layer.guards.reservation_state_guard import (
    ReservationTransitionStateMachine,
)
from app.dispatching.control_layer.guards.verifier_distinct_guard import (
    VerifierDistinctPolicy,
)
from app.dispatching.control_layer.reservation_context import ReservationContext
from app.dispatching.models.enums import ReservationStatus, ReservationType
from app.dispatching.tests.base import DispatchingTestCase


class ReservationTransitionStateMachineTestCase(DispatchingTestCase):
    def test_tentative_to_confirmed_is_legal(self):
        verdict = ReservationTransitionStateMachine.check(
            from_status=ReservationStatus.TENTATIVE, to_status=ReservationStatus.CONFIRMED
        )
        self.assertTrue(verdict.allowed)

    def test_returned_is_terminal(self):
        verdict = ReservationTransitionStateMachine.check(
            from_status=ReservationStatus.RETURNED, to_status=ReservationStatus.CONFIRMED
        )
        self.assertFalse(verdict.allowed)

    def test_tentative_cannot_jump_to_checked_out(self):
        verdict = ReservationTransitionStateMachine.check(
            from_status=ReservationStatus.TENTATIVE, to_status=ReservationStatus.CHECKED_OUT
        )
        self.assertFalse(verdict.allowed)

    def test_same_status_is_refused(self):
        verdict = ReservationTransitionStateMachine.check(
            from_status=ReservationStatus.CONFIRMED, to_status=ReservationStatus.CONFIRMED
        )
        self.assertFalse(verdict.allowed)


class DoubleBookingPolicyTestCase(DispatchingTestCase):
    def _reserve(self, *, asset, start, end, status=ReservationStatus.CONFIRMED):
        reservation = ReservationFactory.create(
            asset_id=asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=start, scheduled_end=end,
            actor=self.actor,
        )
        if status != ReservationStatus.TENTATIVE:
            reservation.reservation_status = status
            reservation.save(update_fields=["reservation_status"])
        return reservation

    def test_confirming_overlapping_confirmed_booking_blocks_without_acknowledgement(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        self._reserve(asset=self.asset, start=start, end=end, status=ReservationStatus.CONFIRMED)

        overlapping = self._reserve(
            asset=self.asset, start=start + timedelta(hours=1), end=end + timedelta(hours=1),
            status=ReservationStatus.TENTATIVE,
        )
        verdict = DoubleBookingPolicy.check_confirm(reservation=overlapping, acknowledge_conflict=False)
        self.assertTrue(verdict.blocks)
        self.assertTrue(verdict.has_conflict)

    def test_confirming_overlapping_confirmed_booking_succeeds_with_acknowledgement(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        self._reserve(asset=self.asset, start=start, end=end, status=ReservationStatus.CONFIRMED)

        overlapping = self._reserve(
            asset=self.asset, start=start + timedelta(hours=1), end=end + timedelta(hours=1),
            status=ReservationStatus.TENTATIVE,
        )
        verdict = DoubleBookingPolicy.check_confirm(reservation=overlapping, acknowledge_conflict=True)
        self.assertFalse(verdict.blocks)
        self.assertTrue(verdict.has_conflict)

    def test_confirming_against_a_tentative_overlap_never_blocks(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        self._reserve(asset=self.asset, start=start, end=end, status=ReservationStatus.TENTATIVE)

        overlapping = self._reserve(
            asset=self.asset, start=start, end=end, status=ReservationStatus.TENTATIVE,
        )
        verdict = DoubleBookingPolicy.check_confirm(reservation=overlapping, acknowledge_conflict=False)
        self.assertFalse(verdict.blocks)

    def test_non_overlapping_windows_never_conflict(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        self._reserve(asset=self.asset, start=start, end=end, status=ReservationStatus.CONFIRMED)

        later = self._reserve(
            asset=self.asset, start=end + timedelta(hours=1), end=end + timedelta(hours=5),
            status=ReservationStatus.TENTATIVE,
        )
        verdict = DoubleBookingPolicy.check_confirm(reservation=later, acknowledge_conflict=False)
        self.assertFalse(verdict.has_conflict)

    def test_maintenance_type_bookings_are_included_automatically(self):
        """No special case: a maintenance-type reservation blocks like any other."""
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=4)
        maint = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.MAINTENANCE,
            accountable_person_id=self.actor.pk, scheduled_start=start, scheduled_end=end, actor=self.actor,
        )
        maint.reservation_status = ReservationStatus.CONFIRMED
        maint.save(update_fields=["reservation_status"])

        overlapping = self._reserve(asset=self.asset, start=start, end=end, status=ReservationStatus.TENTATIVE)
        verdict = DoubleBookingPolicy.check_confirm(reservation=overlapping, acknowledge_conflict=False)
        self.assertTrue(verdict.blocks)


class AccountablePersonPolicyTestCase(DispatchingTestCase):
    def test_accountable_person_passes(self):
        reservation = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1), actor=self.actor,
        )
        AccountablePersonPolicy.check(reservation=reservation, actor=self.actor)  # no raise

    def test_non_accountable_person_is_refused(self):
        reservation = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1), actor=self.actor,
        )
        with self.assertRaises(ValueError):
            AccountablePersonPolicy.check(reservation=reservation, actor=self.other_user)


class VerifierDistinctPolicyTestCase(DispatchingTestCase):
    def test_different_verifier_passes(self):
        VerifierDistinctPolicy.check(verifier=self.actor, self_service_actor_id=self.other_user.pk)

    def test_same_person_is_refused(self):
        with self.assertRaises(ValueError):
            VerifierDistinctPolicy.check(verifier=self.actor, self_service_actor_id=self.actor.pk)


class ReservationDeletionPolicyTestCase(DispatchingTestCase):
    def test_no_handover_allows_deletion(self):
        reservation = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1), actor=self.actor,
        )
        ReservationDeletionPolicy.check(reservation=reservation)  # no raise

    def test_physical_checkout_blocks_deletion(self):
        reservation = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1), actor=self.actor,
        )
        reservation.physical_checkout_at = timezone.now()
        reservation.save(update_fields=["physical_checkout_at"])
        with self.assertRaises(ValueError):
            ReservationDeletionPolicy.check(reservation=reservation)

    def test_context_delete_respects_the_guard(self):
        reservation = ReservationFactory.create(
            asset_id=self.asset.pk, domain_id=self.domain.pk, reservation_type=ReservationType.WORK,
            accountable_person_id=self.actor.pk, scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1), actor=self.actor,
        )
        ctx = ReservationContext(reservation.pk, self.actor)
        ctx.delete()
        reservation.refresh_from_db()
        self.assertIsNotNone(reservation.deleted_at)
