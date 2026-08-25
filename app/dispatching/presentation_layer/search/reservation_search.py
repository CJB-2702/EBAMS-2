"""Read helpers for the reservation screens — the filtered list, the summary
tiles, and the month grid that sits beside them.

The calendar is server-rendered from the *same* queryset the list below it
shows. That is deliberate and is the one place this diverges from the legacy
`my-requests` page, whose FullCalendar fetched its own events from a separate
API and so drifted out of step with the filters directly above it. Here the
filter range **is** the calendar range, which is what makes "show all items in
the filter range on the calendar" true rather than approximately true — and it
keeps the screen working under a plain reload with no JavaScript at all
(harness/Architecture/patterns/htmx_patterns.md, the F5 rule).
"""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from app.dispatching.models.enums import ReservationStatus
from app.dispatching.models.reservations.asset_reservation import AssetReservation

#: Statuses that mean the asset is out right now.
OUT_STATUSES = frozenset(
    {
        ReservationStatus.USER_CHECKED_OUT,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.USER_RETURNED,
    }
)

#: Statuses a booking can still move on from — the "open" bucket.
OPEN_STATUSES = frozenset(
    {
        ReservationStatus.TENTATIVE,
        ReservationStatus.CONFIRMED,
        *OUT_STATUSES,
    }
)

#: Per-status swatch, shared by the calendar chips, the list rows, and the
#: legend so all three can never disagree.
STATUS_TONE: dict[str, str] = {
    ReservationStatus.TENTATIVE: "is-warning",
    ReservationStatus.CONFIRMED: "is-info",
    ReservationStatus.USER_CHECKED_OUT: "is-link",
    ReservationStatus.CHECKED_OUT: "is-primary",
    ReservationStatus.USER_RETURNED: "is-success",
    ReservationStatus.RETURNED: "is-success",
    ReservationStatus.CANCELLED: "is-danger",
    ReservationStatus.NO_SHOW: "is-danger",
}


def status_tone(status: str) -> str:
    return STATUS_TONE.get(status, "is-light")


# ─────────────────────────────────────────────────────────────────────────
# Window
# ─────────────────────────────────────────────────────────────────────────

def parse_date(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def month_bounds(anchor: date) -> tuple[date, date]:
    """First and last day of ``anchor``'s month, inclusive."""
    first = anchor.replace(day=1)
    last = anchor.replace(day=_calendar.monthrange(anchor.year, anchor.month)[1])
    return first, last


def default_window() -> tuple[date, date]:
    """This month — the list's default filter range."""
    return month_bounds(timezone.localdate())


def shift_month(anchor: date, delta: int) -> date:
    """``anchor`` moved ``delta`` whole months, snapped to the 1st."""
    month_index = anchor.year * 12 + (anchor.month - 1) + delta
    return date(month_index // 12, month_index % 12 + 1, 1)


def as_aware_range(window_start: date, window_end: date) -> tuple[datetime, datetime]:
    """Inclusive date range -> half-open aware datetime range."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(window_start, time.min), tz)
    end = timezone.make_aware(datetime.combine(window_end + timedelta(days=1), time.min), tz)
    return start, end


# ─────────────────────────────────────────────────────────────────────────
# The filtered query
# ─────────────────────────────────────────────────────────────────────────

def search_reservations(
    *,
    q: str = "",
    asset: str = "",
    asset_class: str = "",
    domain: str = "",
    status: str = "",
    reservation_type: str = "",
    accountable_person: str = "",
    window_start: date | None = None,
    window_end: date | None = None,
    mine_only: bool = False,
    actor=None,
    domain_ids: list[int] | None = None,
) -> QuerySet[AssetReservation]:
    """Reservations overlapping the window, narrowed by the filter card.

    Overlap, not containment: a booking that starts in March and ends in April
    belongs on both months' calendars. Containment would hide exactly the long
    bookings a scheduler most needs to see.
    """
    qs = (
        AssetReservation.objects.filter(deleted_at__isnull=True)
        .select_related(
            "asset", "asset__asset_class", "asset__model", "domain",
            "accountable_person", "dispatch",
        )
        .order_by("scheduled_start", "pk")
    )

    if domain_ids is not None:
        qs = qs.filter(domain_id__in=domain_ids)

    if window_start is not None and window_end is not None:
        start, end = as_aware_range(window_start, window_end)
        qs = qs.filter(scheduled_start__lt=end, scheduled_end__gte=start)

    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__serial_number__icontains=q)
            | Q(origin__icontains=q)
            | Q(destination__icontains=q)
        )
    if asset:
        if asset.isdigit():
            qs = qs.filter(Q(asset_id=int(asset)) | Q(asset__serial_number__icontains=asset))
        else:
            qs = qs.filter(asset__serial_number__icontains=asset)
    if asset_class:
        qs = qs.filter(asset__asset_class_id=asset_class)
    if domain:
        qs = qs.filter(domain_id=domain)
    if status:
        qs = qs.filter(reservation_status=status)
    if reservation_type:
        qs = qs.filter(reservation_type=reservation_type)
    if accountable_person:
        qs = qs.filter(accountable_person_id=accountable_person)
    if mine_only and actor is not None:
        qs = qs.filter(Q(accountable_person_id=actor.pk) | Q(created_by_id=actor.pk))

    return qs


def summarise(reservations: list[AssetReservation]) -> dict:
    """The four tiles in the rail beside the calendar. Counted in Python off
    the already-materialised page rather than issuing four more COUNT queries
    — the window is one month, so the list is small by construction."""
    now = timezone.now()
    return {
        "total": len(reservations),
        "tentative": sum(
            1 for r in reservations if r.reservation_status == ReservationStatus.TENTATIVE
        ),
        "confirmed": sum(
            1 for r in reservations if r.reservation_status == ReservationStatus.CONFIRMED
        ),
        "out": sum(1 for r in reservations if r.reservation_status in OUT_STATUSES),
        "overdue": sum(
            1
            for r in reservations
            if r.reservation_status in OUT_STATUSES and r.scheduled_end < now
        ),
    }


# ─────────────────────────────────────────────────────────────────────────
# Month grid
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class CalendarDay:
    day: date
    in_month: bool
    is_today: bool
    reservations: list[AssetReservation] = field(default_factory=list)


def build_month_grid(
    *, reservations: list[AssetReservation], anchor: date
) -> list[list[CalendarDay]]:
    """``anchor``'s month as weeks of ``CalendarDay``, each carrying the
    reservations live on that day.

    A booking appears on every day it spans, not only its start — the question
    the calendar answers is "what is out on the 14th", which a start-day-only
    chip cannot answer.
    """
    today = timezone.localdate()
    weeks = _calendar.Calendar(firstweekday=6).monthdatescalendar(anchor.year, anchor.month)

    spans: list[tuple[date, date, AssetReservation]] = []
    for reservation in reservations:
        spans.append(
            (
                timezone.localtime(reservation.scheduled_start).date(),
                timezone.localtime(reservation.scheduled_end).date(),
                reservation,
            )
        )

    grid: list[list[CalendarDay]] = []
    for week in weeks:
        row: list[CalendarDay] = []
        for day in week:
            row.append(
                CalendarDay(
                    day=day,
                    in_month=(day.month == anchor.month),
                    is_today=(day == today),
                    reservations=[r for start, end, r in spans if start <= day <= end],
                )
            )
        grid.append(row)
    return grid
