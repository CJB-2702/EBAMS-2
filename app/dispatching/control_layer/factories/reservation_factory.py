"""Factory: creates a tentative AssetReservation — standalone or attached to
a dispatch at creation time. Always lands Tentative
(dispatching_starter_kit/3_asset_reservations.md §9 — "anyone may place a
tentative claim; only a dispatcher promotes it to confirmed")."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.narrators.reservation_narrator import ReservationNarrator
from app.dispatching.models.enums import ReservationStatus
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.events.models.event import ActivityThreadType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ReservationFactory:
    @classmethod
    def create(
        cls,
        *,
        asset_id: int,
        domain_id: int,
        reservation_type: str,
        accountable_person_id: int,
        scheduled_start,
        scheduled_end,
        dispatch_id: int | None = None,
        origin: str = "",
        destination: str = "",
        title: str = "",
        description: str = "",
        actor: "AbstractUser",
    ) -> AssetReservation:
        if scheduled_start >= scheduled_end:
            raise ValueError("scheduled_start must be before scheduled_end.")

        from app.administration.models import User

        asset = None
        accountable_person = User.objects.get(pk=accountable_person_id)
        if not title:
            from app.assets.models import Asset

            asset = Asset.objects.get(pk=asset_id)
            title = f"Reservation — {asset.name}"

        with transaction.atomic():
            reservation = AssetReservation.objects.create(
                thread_type=ActivityThreadType.EVENT,
                domain_id=domain_id,
                title=title,
                description=description,
                asset_id=asset_id,
                dispatch_id=dispatch_id,
                reservation_type=reservation_type,
                reservation_status=ReservationStatus.TENTATIVE,
                accountable_person_id=accountable_person_id,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                origin=origin,
                destination=destination,
                created_by=actor,
                updated_by=actor,
            )

        from app.events.control_layer.event_context import EventContext

        asset_name = asset.name if asset is not None else f"asset #{asset_id}"
        EventContext(reservation.pk, actor).add_comment(
            {
                "content": ReservationNarrator.created(
                    asset_name=asset_name,
                    scheduled_start=scheduled_start,
                    scheduled_end=scheduled_end,
                    accountable_name=getattr(accountable_person, "username", str(accountable_person_id)),
                )
            },
            is_human_made=False,
        )
        if dispatch_id is not None:
            from app.dispatching.control_layer.guards.dispatch_state_guard import (
                DispatchStateDeriver,
            )

            DispatchStateDeriver.apply(dispatch_id=dispatch_id, actor=actor)
        return reservation
