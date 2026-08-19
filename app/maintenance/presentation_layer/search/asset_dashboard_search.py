"""Search: the fleet-health dashboard's asset list, filtered from a maintenance
angle (planned/started events in a window, active blockers, active
limitations) rather than an asset angle (the assets app's own search.py owns
that). Every filter here reaches through ``Asset.maintenance_details`` (the
reverse FK from events.MaintenanceDetail), so this belongs in maintenance, not
assets.

``index_list`` returns one row per matching asset even when an asset has many
matching maintenance_details — every relational filter below calls
``.distinct()`` for that reason. The per-card detail (next planned events,
active blockers/limitations) is intentionally NOT loaded here: that is a
separate bulk fetch in ``AssetMaintenanceDashboardBuilder``
(control_layer/domain_structs/asset_maintenance_dashboard_struct.py) sized to
one page of results, so this list query stays cheap regardless of page size.
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet

from app.assets.models import Asset
from app.maintenance.models.asset_limitation import AssetLimitationRecord
from app.maintenance.models.blocker import MaintenanceBlocker


def _active_blocker_exists() -> Exists:
    """``Asset.filter(blockers__end_date__isnull=True, ...)`` would also match
    assets with NO blockers at all — the reverse-relation LEFT JOIN makes a
    missing row's ``end_date`` read as NULL too, which satisfies
    ``isnull=True`` just as an actually-open blocker would. ``Exists`` sidesteps
    that by testing for a matching row rather than testing a nullable column
    reached through an outer join."""
    return Exists(
        MaintenanceBlocker.objects.filter(
            maintenance_detail__asset_id=OuterRef("pk"),
            maintenance_detail__deleted_at__isnull=True,
            end_date__isnull=True,
            deleted_at__isnull=True,
        )
    )


def _active_limitation_exists() -> Exists:
    return Exists(
        AssetLimitationRecord.objects.filter(
            maintenance_detail__asset_id=OuterRef("pk"),
            maintenance_detail__deleted_at__isnull=True,
            end_time__isnull=True,
            deleted_at__isnull=True,
        )
    )


class AssetDashboardSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        q: str = "",
        asset_class: str = "",
        model: str = "",
        manufacturer: str = "",
        planned_date_from=None,
        planned_date_to=None,
        started_date_from=None,
        started_date_to=None,
        has_blockers: bool = False,
        has_limitations: bool = False,
    ) -> QuerySet[Asset]:
        """The assets-dashboard's one list read (D5-scoped on ``Asset.domain``).

        ``q`` matches name, serial number, or numeric pk (the "asset id"
        filter) in one field per the search bar convention.
        """
        qs = (
            Asset.objects.filter(domain_id__in=domain_ids, is_active=True)
            .select_related("asset_class", "model", "domain")
            .prefetch_related("model__manufacturers")
        )

        q = (q or "").strip()
        if q:
            id_match = Q(pk=int(q)) if q.isdigit() else Q()
            qs = qs.filter(
                id_match
                | Q(name__icontains=q)
                | Q(serial_number__icontains=q)
            )
        if asset_class:
            qs = qs.filter(asset_class_id=asset_class)
        if model:
            qs = qs.filter(model_id=model)
        if manufacturer:
            qs = qs.filter(model__manufacturers__id=manufacturer)

        if planned_date_from or planned_date_to:
            planned = Q(
                maintenance_details__status="planned",
                maintenance_details__deleted_at__isnull=True,
            )
            if planned_date_from:
                planned &= Q(maintenance_details__event_start__gte=planned_date_from)
            if planned_date_to:
                planned &= Q(maintenance_details__event_start__lte=planned_date_to)
            qs = qs.filter(planned)

        if started_date_from or started_date_to:
            started = Q(
                maintenance_details__status="in_progress",
                maintenance_details__deleted_at__isnull=True,
            )
            if started_date_from:
                started &= Q(maintenance_details__event_start__gte=started_date_from)
            if started_date_to:
                started &= Q(maintenance_details__event_start__lte=started_date_to)
            qs = qs.filter(started)

        if has_blockers:
            qs = qs.filter(_active_blocker_exists())
        if has_limitations:
            qs = qs.filter(_active_limitation_exists())

        needs_distinct = any(
            [
                planned_date_from, planned_date_to,
                started_date_from, started_date_to,
                manufacturer,
            ]
        )
        if needs_distinct:
            qs = qs.distinct()

        return qs.order_by("name")

    @classmethod
    def key_metrics(cls, *, domain_ids) -> dict:
        """Fleet-wide totals for the top metric strip. Deliberately independent
        of the list filters below it — the strip answers "how healthy is the
        whole fleet", not "how many of my filtered results are healthy"."""
        active_assets = Asset.objects.filter(domain_id__in=domain_ids, is_active=True)
        blocked = active_assets.filter(_active_blocker_exists())
        limited = active_assets.filter(_active_limitation_exists())
        return {
            "active_assets": active_assets.count(),
            "blocked_assets": blocked.count(),
            "limited_assets": limited.count(),
        }
