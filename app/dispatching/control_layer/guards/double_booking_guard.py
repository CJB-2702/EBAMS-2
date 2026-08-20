"""Guard type: Policy. Overlap detection for one asset's schedule
(dispatching_starter_kit/3_asset_reservations.md §10).

Tentative bookings never block anything and are never themselves blocked by
this guard — only Confirmed-or-later state matters for the "may I confirm"
question. Maintenance is included automatically: it is a ReservationType,
not a special case, so the same query already covers it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dispatching.models.enums import ReservationStatus
from app.dispatching.models.reservations.asset_reservation import AssetReservation

#: Statuses that occupy the asset for overlap purposes on a read-side
#: availability check (includes tentative holds, since a competing tentative
#: claim is still a fact worth surfacing).
LIVE_STATUSES = frozenset(
    {
        ReservationStatus.TENTATIVE,
        ReservationStatus.CONFIRMED,
        ReservationStatus.USER_CHECKED_OUT,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    }
)

#: Statuses that block a *confirm* — Tentative overlaps only ever warn.
CONFIRMED_LIKE_STATUSES = frozenset(
    {
        ReservationStatus.CONFIRMED,
        ReservationStatus.USER_CHECKED_OUT,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    }
)


@dataclass(frozen=True)
class OverlapVerdict:
    has_conflict: bool
    blocks: bool
    conflicting_reservation_ids: list[int] = field(default_factory=list)


class DoubleBookingPolicy:
    """Policy: may this asset's window be claimed without conflict?"""

    @classmethod
    def find_overlaps(
        cls,
        *,
        asset_id: int,
        scheduled_start,
        scheduled_end,
        statuses: frozenset[str] = LIVE_STATUSES,
        exclude_reservation_id: int | None = None,
    ) -> list[AssetReservation]:
        qs = AssetReservation.objects.filter(
            asset_id=asset_id,
            deleted_at__isnull=True,
            reservation_status__in=statuses,
            scheduled_start__lt=scheduled_end,
            scheduled_end__gt=scheduled_start,
        )
        if exclude_reservation_id is not None:
            qs = qs.exclude(pk=exclude_reservation_id)
        return list(qs)

    @classmethod
    def check_confirm(cls, *, reservation: AssetReservation, acknowledge_conflict: bool) -> OverlapVerdict:
        conflicts = cls.find_overlaps(
            asset_id=reservation.asset_id,
            scheduled_start=reservation.scheduled_start,
            scheduled_end=reservation.scheduled_end,
            statuses=CONFIRMED_LIKE_STATUSES,
            exclude_reservation_id=reservation.pk,
        )
        if not conflicts:
            return OverlapVerdict(has_conflict=False, blocks=False)
        conflict_ids = [r.pk for r in conflicts]
        if acknowledge_conflict:
            return OverlapVerdict(has_conflict=True, blocks=False, conflicting_reservation_ids=conflict_ids)
        return OverlapVerdict(has_conflict=True, blocks=True, conflicting_reservation_ids=conflict_ids)
