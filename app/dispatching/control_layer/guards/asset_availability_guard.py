"""Guard type: Policy. Read-side "is this asset free for this window?" —
used by calendars and RequestedAssetAutoReserver (doc 2 §4.2). Includes
maintenance-type bookings automatically: no special case, the same
reservation table and query already covers them (doc 3 §10)."""

from __future__ import annotations

from app.dispatching.control_layer.guards.double_booking_guard import (
    LIVE_STATUSES,
    DoubleBookingPolicy,
)


class AssetAvailabilityPolicy:
    @classmethod
    def is_available(
        cls,
        *,
        asset_id: int,
        scheduled_start,
        scheduled_end,
        exclude_reservation_id: int | None = None,
    ) -> bool:
        overlaps = DoubleBookingPolicy.find_overlaps(
            asset_id=asset_id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            statuses=LIVE_STATUSES,
            exclude_reservation_id=exclude_reservation_id,
        )
        return not overlaps
