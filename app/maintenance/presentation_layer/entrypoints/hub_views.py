"""The merged maintenance hub.

Legacy had four screens here: a role-chooser index and three portal dashboards
(manager, technician, fleet). They collapse into this one page — the fleet
portal contributed only stat tiles (its body was a "will be implemented here"
placeholder) and the role chooser was navigation dressed as a page.

Composition, per legacy_ui/gap_analysis.md §7:
  1. one stat strip — the union of all four screens, deduplicated
  2. a "My Work" band  — the technician content
  3. a "Manage" band   — the four manager workflow cards

Band visibility is the one place Rule #5's "cards always render" does NOT
apply: a whole band belonging to work the user has none of is the rule's
"feature doesn't apply" exception. An empty CARD inside a band the user does
see still renders with its empty state.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.assets.models.core.asset import Asset
from app.events.models.details.maintenance import MaintenanceDetail
from app.maintenance.models.asset_limitation import AssetLimitationRecord
from app.maintenance.models.blocker import MaintenanceBlocker
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.models.planning.maintenance_plan import MaintenancePlan
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.search.maintenance_demand_search import (
    MaintenanceDemandSearch,
    SCOPE_MAINTENANCE,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
)
from app.procurement.models import DemandState
from app.procurement.presentation_layer.tools.procurement_access import (
    can_manage_demand,
)

OPEN_STATUSES = ("planned", "in_progress", "blocked")
CLOSED_STATUSES = ("completed", "cancelled")

#: How far ahead "Planned this week" looks. Seven days, not "this calendar
#: week" — a technician on Friday cares about the next seven days, not about
#: two days and then a cliff.
LOOKAHEAD_DAYS = 7


@require_http_methods(["GET"])
def maintenance_hub(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    now = timezone.now()

    events = MaintenanceDetail.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    )
    mine = events.filter(assigned_user_id=request.user.pk)

    demands = MaintenanceDemandSearch.index_list(
        domain_ids=domain_ids, scope=SCOPE_MAINTENANCE
    )

    thirty_days_ago = now - timedelta(days=30)
    thirty_days_future = now + timedelta(days=30)

    stats = {
        "completed_last_30": events.filter(
            status="completed", updated_at__gte=thirty_days_ago
        ).count(),
        "planned_next_30": events.filter(
            status="planned",
            event_start__gte=now,
            event_start__lte=thirty_days_future,
        ).count(),
        "overdue": events.filter(
            event_start__lt=now, status__in=OPEN_STATUSES
        ).count(),
        "active": events.filter(status__in=OPEN_STATUSES).count(),
        "pending_demands": demands.filter(
            demand_state__in=[DemandState.PROJECTED, DemandState.REQUIRED]
        ).count(),
        "assets_with_blocked": Asset.objects.filter(
            domain_id__in=domain_ids
        ).filter(
            pk__in=MaintenanceDetail.objects.filter(
                blockers__end_date__isnull=True, deleted_at__isnull=True
            )
            .values_list("asset_id", flat=True)
            .distinct()
        ).count(),
        "assets_with_limitations": Asset.objects.filter(
            domain_id__in=domain_ids
        ).filter(
            pk__in=MaintenanceDetail.objects.filter(
                limitation_records__end_time__isnull=True, deleted_at__isnull=True
            )
            .values_list("asset_id", flat=True)
            .distinct()
        ).count(),
    }

    my_stats = {
        "assigned": mine.exclude(status__in=CLOSED_STATUSES).count(),
        "in_progress": mine.filter(status="in_progress").count(),
        "completed_today": mine.filter(
            status="completed", updated_at__date=timezone.localdate()
        ).count(),
    }

    return render(
        request,
        "maintenance/hub.html",
        {
            "stats": stats,
            "my_stats": my_stats,
            # The "My Work" band shows whenever the user has any assigned work
            # at all, past or present — otherwise it is not their job and the
            # band is noise.
            "show_my_work": mine.exists(),
            "my_events": mine.exclude(status__in=CLOSED_STATUSES)
            .select_related("asset")
            .order_by("event_start")[:8],
            "planned_this_week": mine.filter(
                event_start__gte=now,
                event_start__lte=now + timedelta(days=LOOKAHEAD_DAYS),
            )
            .exclude(status__in=CLOSED_STATUSES)
            .select_related("asset")
            .order_by("event_start")[:8],
            "recent_events": mine.filter(status__in=CLOSED_STATUSES)
            .select_related("asset")
            .order_by("-updated_at")[:5],
            "attention_events": events.filter(status="blocked")
            .select_related("asset", "assigned_user")
            .order_by("event_start")[:5],
            "can_manage_demands": can_manage_demand(request),
        },
    )
