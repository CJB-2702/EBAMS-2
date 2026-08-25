"""Manager: the dual-track handover — self-service (user) and dispatcher
verification, kept as two independent tracks that never overwrite each other
(dispatching_starter_kit/3_asset_reservations.md §7.2). Rebuilt against the
new schema after reading legacy's checkout_manager.py, per
build_phase_2_control_layer.md §1.2 — the dual-track semantics are correct
there and are reproduced faithfully; the SQLAlchemy structure is not.

Workflow: Confirmed -> [User Checkout] -> Dispatcher Verifies Checkout ->
[User Check-In] -> Dispatcher Verifies Return. The dispatcher may also
verify checkout/return directly without a preceding self-service step.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.dispatching.control_layer.guards.accountable_person_guard import (
    AccountablePersonPolicy,
)
from app.dispatching.control_layer.guards.reservation_state_guard import (
    ReservationTransitionStateMachine,
)
from app.dispatching.control_layer.guards.verifier_distinct_guard import (
    VerifierDistinctPolicy,
)
from app.dispatching.control_layer.narrators.reservation_narrator import ReservationNarrator
from app.dispatching.models.enums import ReservationStatus, ReservationUpdateChangeType


class ReservationCheckoutManager:
    def __init__(self, reservation_context) -> None:
        self._ctx = reservation_context

    @property
    def reservation(self):
        return self._ctx.reservation

    @property
    def actor(self):
        return self._ctx.actor

    def _transition(self, *, to_status: str) -> None:
        verdict = ReservationTransitionStateMachine.check(
            from_status=self.reservation.reservation_status, to_status=to_status
        )
        if not verdict.allowed:
            raise ValueError(verdict.reason)

    # ------------------------------------------------------------------ #
    # 1. User checkout — self-service
    # ------------------------------------------------------------------ #

    def user_checkout(
        self,
        *,
        condition: str = "",
        notes: str = "",
        meter1: float | None = None,
        meter2: float | None = None,
        on_behalf: bool = False,
    ):
        """meter1/meter2 are what the user says they read. They are stored on
        the reservation and go no further — no MeterHistory row, no change to
        Asset.meterN. Only dispatcher_verify_* makes a meter official."""
        AccountablePersonPolicy.check(
            reservation=self.reservation, actor=self.actor, on_behalf=on_behalf
        )
        self._transition(to_status=ReservationStatus.USER_CHECKED_OUT)

        reservation = self.reservation
        with transaction.atomic():
            reservation.user_checkout_submitted_at = timezone.now()
            reservation.user_checked_out_by = self.actor
            reservation.user_reported_condition_out = condition
            reservation.user_checkout_notes = notes
            reservation.user_meter1_out = meter1
            reservation.user_meter2_out = meter2
            reservation.reservation_status = ReservationStatus.USER_CHECKED_OUT
            reservation.updated_by = self.actor
            reservation.save()
            self._ctx._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                previous_value=ReservationStatus.CONFIRMED,
                new_value=ReservationStatus.USER_CHECKED_OUT,
            )
        self._ctx._narrate(
            ReservationNarrator.user_checked_out(actor=self.actor, condition=condition or None)
        )
        self._ctx._derive_dispatch_state()
        self._ctx.refresh()
        return self.reservation

    # ------------------------------------------------------------------ #
    # 2. Dispatcher verifies checkout — authoritative
    # ------------------------------------------------------------------ #

    def dispatcher_verify_checkout(
        self,
        *,
        checked_out_at=None,
        condition: str = "",
        notes: str = "",
        readings: dict[int, float] | None = None,
    ):
        """``readings`` maps meter index -> value and IS an official meter
        update: it writes MeterHistory and moves Asset.meterN. That is the
        difference between this track and the user's."""
        VerifierDistinctPolicy.check(
            verifier=self.actor, self_service_actor_id=self.reservation.user_checked_out_by_id
        )
        if self.reservation.reservation_status != ReservationStatus.USER_RETURNED:
            self._transition(to_status=ReservationStatus.CHECKED_OUT)
            target_status = ReservationStatus.CHECKED_OUT
        else:
            target_status = ReservationStatus.USER_RETURNED

        reservation = self.reservation
        with transaction.atomic():
            reservation.physical_checkout_at = checked_out_at or timezone.now()
            reservation.condition_out = condition
            reservation.dispatcher_checkout_notes = notes
            reservation.checkout_verified_by = self.actor
            reservation.checkout_verified_at = timezone.now()
            reservation.reservation_status = target_status
            reservation.updated_by = self.actor
            reservation.save()

            if readings:
                from app.dispatching.control_layer.managers.meter_read_recorder import (
                    MeterReadRecorder,
                )

                MeterReadRecorder.record_initial(
                    reservation=reservation, readings=readings,
                    actor=self.actor, recorded_at=reservation.physical_checkout_at,
                )

            self._ctx._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                new_value=ReservationStatus.CHECKED_OUT,
            )
        self._ctx._narrate(
            ReservationNarrator.dispatcher_checkout_verified(actor=self.actor, condition=condition or None)
        )
        self._ctx._derive_dispatch_state()
        self._ctx.refresh()
        return self.reservation

    # ------------------------------------------------------------------ #
    # 3. User check-in — self-service return
    # ------------------------------------------------------------------ #

    def user_checkin(
        self,
        *,
        condition: str = "",
        notes: str = "",
        meter1: float | None = None,
        meter2: float | None = None,
        on_behalf: bool = False,
    ):
        """As user_checkout: the meters here are reference information only."""
        AccountablePersonPolicy.check(
            reservation=self.reservation, actor=self.actor, on_behalf=on_behalf
        )
        self._transition(to_status=ReservationStatus.USER_RETURNED)

        reservation = self.reservation
        with transaction.atomic():
            reservation.user_checkin_submitted_at = timezone.now()
            reservation.user_checked_in_by = self.actor
            reservation.user_reported_condition_in = condition
            reservation.user_checkin_notes = notes
            reservation.user_meter1_in = meter1
            reservation.user_meter2_in = meter2
            reservation.reservation_status = ReservationStatus.USER_RETURNED
            reservation.updated_by = self.actor
            reservation.save()
            self._ctx._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                previous_value=ReservationStatus.CHECKED_OUT,
                new_value=ReservationStatus.USER_RETURNED,
            )
        self._ctx._narrate(
            ReservationNarrator.user_checked_in(actor=self.actor, condition=condition or None)
        )
        self._ctx._derive_dispatch_state()
        self._ctx.refresh()
        return self.reservation

    # ------------------------------------------------------------------ #
    # 4. Dispatcher verifies return — authoritative
    # ------------------------------------------------------------------ #

    def dispatcher_verify_return(
        self,
        *,
        checked_in_at=None,
        condition: str = "",
        notes: str = "",
        readings: dict[int, float] | None = None,
    ):
        """As dispatcher_verify_checkout: ``readings`` is an official update."""
        VerifierDistinctPolicy.check(
            verifier=self.actor, self_service_actor_id=self.reservation.user_checked_in_by_id
        )
        self._transition(to_status=ReservationStatus.RETURNED)

        reservation = self.reservation
        checked_in_at = checked_in_at or timezone.now()
        if reservation.physical_checkout_at and checked_in_at < reservation.physical_checkout_at:
            raise ValueError("Return time must be on or after checkout time.")

        with transaction.atomic():
            reservation.physical_checkin_at = checked_in_at
            reservation.condition_in = condition
            reservation.dispatcher_checkin_notes = notes
            reservation.return_verified_by = self.actor
            reservation.return_verified_at = timezone.now()
            reservation.reservation_status = ReservationStatus.RETURNED
            reservation.updated_by = self.actor
            reservation.save()

            if readings:
                from app.dispatching.control_layer.managers.meter_read_recorder import (
                    MeterReadRecorder,
                )

                MeterReadRecorder.record_final(
                    reservation=reservation, readings=readings,
                    actor=self.actor, recorded_at=checked_in_at,
                )

            self._ctx._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                new_value=ReservationStatus.RETURNED,
            )
        self._ctx._narrate(
            ReservationNarrator.dispatcher_return_verified(actor=self.actor, condition=condition or None)
        )
        self._ctx._derive_dispatch_state()
        self._ctx.refresh()
        return self.reservation
