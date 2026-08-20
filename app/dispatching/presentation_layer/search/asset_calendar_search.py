"""Read helpers for asset availability over a window — calendars and
booking screens. Queries reservations directly; there is no separate
"dispatch assets" table to join through (design_drift.md §2.4)."""

from __future__ import annotations

from django.db.models import QuerySet

from app.dispatching.control_layer.guards.double_booking_guard import LIVE_STATUSES
from app.dispatching.models.reservations.asset_reservation import AssetReservation


def search_reservations_for_asset(
    *, asset_id: int, window_start=None, window_end=None
) -> QuerySet[AssetReservation]:
    qs = AssetReservation.objects.filter(
        asset_id=asset_id, deleted_at__isnull=True
    ).select_related("dispatch", "accountable_person").order_by("scheduled_start")
    if window_start is not None:
        qs = qs.filter(scheduled_end__gte=window_start)
    if window_end is not None:
        qs = qs.filter(scheduled_start__lte=window_end)
    return qs


def search_live_reservations_in_window(
    *, window_start, window_end, domain_ids=None
) -> QuerySet[AssetReservation]:
    """Reservations that occupy asset capacity over the window — the source
    query behind AssetAvailabilityPolicy and the fleet calendar alike."""
    qs = AssetReservation.objects.filter(
        deleted_at__isnull=True,
        reservation_status__in=LIVE_STATUSES,
        scheduled_start__lt=window_end,
        scheduled_end__gt=window_start,
    ).select_related("asset", "dispatch", "accountable_person")
    if domain_ids is not None:
        qs = qs.filter(domain_id__in=domain_ids)
    return qs
