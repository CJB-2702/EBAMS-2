"""Manager: on submission, tentatively holds the assets the requester named
that are actually free for the window, and skips the contested ones — the
dispatcher decides those (dispatching_starter_kit/2_dispatch.md §4.2, R3,
R4).

Deliberately does NOT read DispatchingDetail.requested_assets — that field
is free text, written once, and never a source for anything the system
parses (§4.1, design_drift.md §2.8, the "never synced" warning). The caller
supplies the structured candidate list explicitly; it is the caller's job
(the submission form/adaptor) to have gathered real asset ids alongside
whatever free text it also stored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dataclasses import dataclass, field

from app.dispatching.control_layer.guards.asset_availability_guard import (
    AssetAvailabilityPolicy,
)
from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.models.enums import ReservationType
from app.dispatching.models.reservations.asset_reservation import AssetReservation

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.models.details.dispatching import DispatchingDetail


@dataclass(frozen=True)
class AutoReserveResult:
    reserved: list[AssetReservation] = field(default_factory=list)
    skipped_asset_ids: list[int] = field(default_factory=list)


class RequestedAssetAutoReserver:
    @classmethod
    def reserve_free_assets(
        cls,
        *,
        dispatch: "DispatchingDetail",
        candidate_asset_ids: list[int],
        actor: "AbstractUser",
    ) -> AutoReserveResult:
        reserved: list[AssetReservation] = []
        skipped: list[int] = []
        for asset_id in candidate_asset_ids:
            is_free = AssetAvailabilityPolicy.is_available(
                asset_id=asset_id,
                scheduled_start=dispatch.desired_start,
                scheduled_end=dispatch.desired_end,
            )
            if not is_free:
                skipped.append(asset_id)
                continue
            reservation = ReservationFactory.create(
                asset_id=asset_id,
                domain_id=dispatch.domain_id,
                reservation_type=ReservationType.WORK,
                accountable_person_id=dispatch.requested_for_id,
                scheduled_start=dispatch.desired_start,
                scheduled_end=dispatch.desired_end,
                dispatch_id=dispatch.pk,
                actor=actor,
            )
            reserved.append(reservation)
        return AutoReserveResult(reserved=reserved, skipped_asset_ids=skipped)
