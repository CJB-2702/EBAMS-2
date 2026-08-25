"""Manager: attaches a standalone reservation to a dispatch — the promotion
boundary (dispatching_starter_kit/3_asset_reservations.md §11.1). One
action, not a rebuild: the reservation keeps its identity, event, history,
and handover record. Narrates on both timelines — its own (a milestone) and,
now that one exists, the dispatch's (doc 4 §5.1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.narrators.reservation_narrator import ReservationNarrator
from app.dispatching.models.enums import ReservationUpdateChangeType
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.events.control_layer.managers.asset_event_link_manager import (
    AssetEventLinkManager,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ReservationPromotionManager:
    @classmethod
    def promote(cls, *, reservation_id: int, dispatch_id: int, actor: "AbstractUser") -> AssetReservation:
        reservation = AssetReservation.objects.get(pk=reservation_id, deleted_at__isnull=True)
        if reservation.dispatch_id is not None:
            raise ValueError(
                f"Reservation #{reservation_id} is already attached to Dispatch "
                f"#{reservation.dispatch_id}."
            )

        with transaction.atomic():
            reservation.dispatch_id = dispatch_id
            reservation.updated_by = actor
            reservation.save(update_fields=["dispatch", "updated_by", "updated_at"])

            from app.dispatching.models.reservations.reservation_update import (
                ReservationUpdate,
            )

            ReservationUpdate.objects.create(
                reservation=reservation,
                change_type=ReservationUpdateChangeType.OTHER,
                field_changed="dispatch",
                new_value=str(dispatch_id),
                reason="Attached to a dispatch.",
                actor=actor,
                created_by=actor,
                updated_by=actor,
            )

            # The dispatch just acquired an asset. ReservationFactory writes
            # this link when the reservation is born attached; promotion is
            # the other way in, and it has to write it too or a promoted
            # reservation's asset stays invisible on the dispatch.
            AssetEventLinkManager.link(
                asset_id=reservation.asset_id,
                event_id=dispatch_id,
                role="reserved_unit",
                actor=actor,
            )

        from app.events.control_layer.event_context import EventContext

        text = ReservationNarrator.promoted_to_dispatch(dispatch_id=dispatch_id)
        EventContext(reservation.pk, actor).add_comment({"content": text}, is_human_made=False)
        EventContext(dispatch_id, actor).add_comment(
            {"content": f"Reservation #{reservation.pk} attached."}, is_human_made=False
        )
        return reservation
