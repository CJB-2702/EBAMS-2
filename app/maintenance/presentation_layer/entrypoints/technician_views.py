"""Technician dashboard — a technician's personal work landing screen.

Legacy: user_views/technician/main.py `dashboard`
(legacy_ui/page_catalog.md #17, screenshot 20_technician_dashboard.png).

The legacy role-chooser and the separate manager/technician/fleet dashboards
were already merged into `maintenance_hub` (gap_analysis.md §7); its "My
Work" band covers the same three stat tiles plus assigned/planned event
lists. This page is the technician's own dedicated landing screen carrying
the fuller card set the legacy dashboard had that the merged hub left out to
stay dense: the asset lookup, a direct link to the event ledger, and a
"recently interacted with" card.

Two legacy widgets are intentionally not ported — see NOT PORTED notes below.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.assets.models import Asset
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventStatus
from app.maintenance.presentation_layer.search.maintenance_search import (
    MaintenanceSearch,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
)

#: How far ahead "Planned this week" looks — matches maintenance_hub's band.
LOOKAHEAD_DAYS = 7

CLOSED_STATUSES = (
    EventStatus.COMPLETE,
    EventStatus.CANCELLED,
    EventStatus.FAILED,
    EventStatus.SKIPPED,
)


@require_http_methods(["GET"])
def technician_dashboard(request: HttpRequest) -> HttpResponse:
    """The technician's personal dashboard (legacy /maintenance/technician/dashboard).

    NOT PORTED — `View Events by Your Location`: the legacy tile derived a
    location from `Event.major_location_id` / `Asset.major_location_id`.
    Neither EBAMS-2's Event nor Asset model carries a location field
    (`administration.Domain` is an access scope, not a place), so there is no
    data to back this tile without a schema change. Skipped rather than
    faked; flagged in the porting report.

    NOT PORTED — the four extra `{% if %}`-guarded widgets in the legacy
    template (Top Assets, Recent Part Demand Updates, Part Demands Needing
    Approval, Part Demands Awaiting Receipt): absent from the reference
    screenshot (empty for the seeded technician) and not mentioned in
    page_catalog.md's card-by-card anatomy. They also duplicate the
    part-demand queue already reachable from the hub's Manage band. Skipped
    as vestigial rather than ported as dead weight.
    """
    if request.GET.get("format") == "htmx-asset-lookup":
        return _asset_lookup_results(request)

    domain_ids = accessible_domain_ids(request)
    now = timezone.now()

    mine = MaintenanceDetail.objects.filter(
        domain_id__in=domain_ids,
        deleted_at__isnull=True,
        assigned_user_id=request.user.pk,
    )

    stats = {
        "assigned_work": mine.exclude(status__in=CLOSED_STATUSES).count(),
        "in_progress": mine.filter(status=EventStatus.IN_PROGRESS).count(),
        "completed_today": mine.filter(
            status=EventStatus.COMPLETE, updated_at__date=timezone.localdate()
        ).count(),
    }

    return render(
        request,
        "maintenance/technician/dashboard.html",
        {
            "stats": stats,
            "assigned_events": mine.exclude(status__in=CLOSED_STATUSES)
            .select_related("asset")
            .order_by("event_start")[:8],
            "planned_this_week": mine.filter(
                event_start__gte=now,
                event_start__lte=now + timedelta(days=LOOKAHEAD_DAYS),
            )
            .exclude(status__in=CLOSED_STATUSES)
            .select_related("asset")
            .order_by("event_start")[:8],
            "recently_interacted": MaintenanceSearch.recently_interacted(
                domain_ids=domain_ids, user_id=request.user.pk, limit=5
            ),
        },
    )


def _asset_lookup_results(request: HttpRequest) -> HttpResponse:
    """Quick Asset Lookup fragment. Legacy redirected on pick; here each
    result is a plain link straight to that asset's filtered event ledger —
    the search-input-driving-a-list pattern (searchbars.md), not a
    `<search-dropdown>` picker, since nothing is being attached to a form."""
    q = request.GET.get("q", "").strip()
    assets = Asset.objects.none()
    if q:
        assets = Asset.objects.filter(
            Q(name__icontains=q) | Q(serial_number__icontains=q)
        ).order_by("name")[:10]
    return render(
        request,
        "maintenance/technician/_asset_lookup_results.html",
        {"assets": assets, "q": q},
    )
