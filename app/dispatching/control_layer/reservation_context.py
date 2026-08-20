"""Context: entry point for control logic around one AssetReservation id.

Owns the reservation lifecycle directly (confirm, cancel, no-show, conflict
acknowledgement, deletion, promotion to a dispatch); delegates the dual-track
handover to ReservationCheckoutManager. Every domain verb writes a typed
ReservationUpdate row (the change log, doc 3 §8) and a machine comment on the
reservation's own Event thread (doc 4 §5.1) — two channels, same transaction
boundary rule as MaintenanceBlockerManager: the row commits, then narration
posts outside that transaction so a comment failure never rolls back the
change it describes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.dispatching.control_layer.domain_structs.reservation_struct import (
    ReservationStruct,
)
from app.dispatching.control_layer.guards.double_booking_guard import DoubleBookingPolicy
from app.dispatching.control_layer.guards.reservation_deletion_guard import (
    ReservationDeletionPolicy,
)
from app.dispatching.control_layer.guards.reservation_state_guard import (
    ReservationTransitionStateMachine,
)
from app.dispatching.control_layer.narrators.reservation_narrator import ReservationNarrator
from app.dispatching.models.enums import ReservationStatus, ReservationUpdateChangeType
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.dispatching.models.reservations.reservation_update import ReservationUpdate

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ReservationContext:
    def __init__(self, reservation_id: int, actor: "AbstractUser") -> None:
        self.actor = actor
        self.struct = ReservationStruct.load(reservation_id=reservation_id)

    @classmethod
    def from_struct(cls, struct: ReservationStruct, actor: "AbstractUser") -> "ReservationContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        return ctx

    @property
    def reservation(self) -> AssetReservation:
        return self.struct.reservation

    def refresh(self) -> None:
        self.struct = ReservationStruct.load(reservation_id=self.reservation.pk)

    # ------------------------------------------------------------------ #
    # Sub-managers
    # ------------------------------------------------------------------ #

    @property
    def checkout(self):
        from app.dispatching.control_layer.managers.reservation_checkout_manager import (
            ReservationCheckoutManager,
        )

        return ReservationCheckoutManager(self)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _record_update(
        self,
        *,
        change_type: str,
        field_changed: str = "",
        previous_value: str = "",
        new_value: str = "",
        reason: str = "",
        is_system_generated: bool = False,
    ) -> ReservationUpdate:
        return ReservationUpdate.objects.create(
            reservation=self.reservation,
            change_type=change_type,
            field_changed=field_changed,
            previous_value=previous_value,
            new_value=new_value,
            reason=reason,
            actor=self.actor,
            is_system_generated=is_system_generated,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def _narrate(self, text: str) -> None:
        """Deliberately outside the write transaction — a comment failing to
        save must not roll back the change it describes."""
        from app.events.control_layer.event_context import EventContext

        EventContext(self.reservation.pk, self.actor).add_comment(
            {"content": text}, is_human_made=False
        )

    def _transition(self, *, to_status: str) -> None:
        verdict = ReservationTransitionStateMachine.check(
            from_status=self.reservation.reservation_status, to_status=to_status
        )
        if not verdict.allowed:
            raise ValueError(verdict.reason)

    def _derive_dispatch_state(self) -> None:
        """Standalone reservations (no dispatch_id) never touch dispatch
        machinery at all — the reservation lifecycle works end to end with
        no dispatch in the database. Only when attached does a status change
        recompute the dispatch's own Planned/AlternateResolution state (R8)."""
        if self.reservation.dispatch_id is None:
            return
        from app.dispatching.control_layer.guards.dispatch_state_guard import (
            DispatchStateDeriver,
        )

        DispatchStateDeriver.apply(dispatch_id=self.reservation.dispatch_id, actor=self.actor)

    # ------------------------------------------------------------------ #
    # Domain verbs
    # ------------------------------------------------------------------ #

    def confirm(self, *, acknowledge_conflict: bool = False, conflict_reason: str = "") -> AssetReservation:
        self._transition(to_status=ReservationStatus.CONFIRMED)
        verdict = DoubleBookingPolicy.check_confirm(
            reservation=self.reservation, acknowledge_conflict=acknowledge_conflict
        )
        if verdict.blocks:
            raise ValueError(
                "This asset already has a confirmed booking overlapping this window "
                f"(reservation(s) {verdict.conflicting_reservation_ids}). Acknowledge "
                "the conflict to confirm anyway."
            )

        reservation = self.reservation
        with transaction.atomic():
            reservation.reservation_status = ReservationStatus.CONFIRMED
            if verdict.has_conflict:
                reservation.conflict_acknowledged_by = self.actor
                reservation.conflict_acknowledged_at = timezone.now()
                reservation.conflict_acknowledgement_reason = conflict_reason
            reservation.updated_by = self.actor
            reservation.save()
            self._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                previous_value=ReservationStatus.TENTATIVE,
                new_value=ReservationStatus.CONFIRMED,
            )
        self._narrate(
            ReservationNarrator.confirmed(actor=self.actor, conflict_acknowledged=verdict.has_conflict)
        )
        self._derive_dispatch_state()
        self.refresh()
        return self.reservation

    def cancel(self, *, reason: str) -> AssetReservation:
        if not (reason or "").strip():
            raise ValueError("A cancellation reason is required.")
        self._transition(to_status=ReservationStatus.CANCELLED)

        reservation = self.reservation
        previous_status = reservation.reservation_status
        with transaction.atomic():
            reservation.reservation_status = ReservationStatus.CANCELLED
            reservation.cancellation_reason = reason
            reservation.cancelled_by = self.actor
            reservation.cancelled_at = timezone.now()
            reservation.updated_by = self.actor
            reservation.save()
            self._record_update(
                change_type=ReservationUpdateChangeType.CANCELLATION,
                field_changed="reservation_status",
                previous_value=previous_status,
                new_value=ReservationStatus.CANCELLED,
                reason=reason,
            )
        self._narrate(ReservationNarrator.cancelled(actor=self.actor, reason=reason))
        self._derive_dispatch_state()
        self.refresh()
        return self.reservation

    def mark_no_show(self) -> AssetReservation:
        self._transition(to_status=ReservationStatus.NO_SHOW)
        reservation = self.reservation
        with transaction.atomic():
            reservation.reservation_status = ReservationStatus.NO_SHOW
            reservation.updated_by = self.actor
            reservation.save()
            self._record_update(
                change_type=ReservationUpdateChangeType.STATUS_TRANSITION,
                field_changed="reservation_status",
                previous_value=ReservationStatus.CONFIRMED,
                new_value=ReservationStatus.NO_SHOW,
            )
        self._narrate(ReservationNarrator.no_show(actor=self.actor))
        self._derive_dispatch_state()
        self.refresh()
        return self.reservation

    def promote_to_dispatch(self, *, dispatch_id: int) -> AssetReservation:
        from app.dispatching.control_layer.managers.reservation_promotion_manager import (
            ReservationPromotionManager,
        )

        result = ReservationPromotionManager.promote(
            reservation_id=self.reservation.pk, dispatch_id=dispatch_id, actor=self.actor
        )
        self.refresh()
        self._derive_dispatch_state()
        return result

    def delete(self) -> None:
        ReservationDeletionPolicy.check(reservation=self.reservation)
        self.reservation._soft_delete(self.actor)
