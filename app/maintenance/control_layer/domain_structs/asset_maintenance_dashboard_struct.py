"""Struct + builder: per-asset maintenance overview for the assets dashboard
large cards.

``AssetMaintenanceDashboardStruct`` is the read model for one card. The
expensive part is the fan-out — three child collections (planned events,
active blockers, active limitations) per asset — so
``AssetMaintenanceDashboardBuilder.build_for_page`` loads all three with three
bulk queries scoped to one page of asset ids and zips them in Python,
instead of N+1 queries per card. Callers must pass one *page* of assets
(``AssetDashboardSearch.index_list`` paginated), not the full fleet.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import QuerySet
from django.utils import timezone

from app.assets.models import Asset
from app.events.models.details.maintenance import MaintenanceDetail
from app.maintenance.models.asset_limitation import AssetLimitationRecord
from app.maintenance.models.blocker import MaintenanceBlocker

#: Per card, per the dashboard spec: "next three maintenance events planned
#: and dates".
NEXT_PLANNED_LIMIT = 3


@dataclass
class AssetMaintenanceDashboardStruct:
    asset: Asset
    next_planned_events: list[MaintenanceDetail] = field(default_factory=list)
    active_blockers: list[MaintenanceBlocker] = field(default_factory=list)
    active_limitation_records: list[AssetLimitationRecord] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return len(self.active_blockers) > 0

    @property
    def has_active_limitation(self) -> bool:
        return len(self.active_limitation_records) > 0

    @property
    def health_status(self) -> str:
        """Blocked outranks limited for the card's single accent color —
        both badges still render, but the rail/border only needs one."""
        if self.is_blocked:
            return "blocked"
        if self.has_active_limitation:
            return "limited"
        return "healthy"


class AssetMaintenanceDashboardBuilder:
    @classmethod
    def build_for_page(
        cls, assets: QuerySet[Asset] | list[Asset]
    ) -> list[AssetMaintenanceDashboardStruct]:
        assets = list(assets)
        asset_ids = [a.pk for a in assets]
        if not asset_ids:
            return []

        now = timezone.now()

        planned_by_asset: dict[int, list[MaintenanceDetail]] = defaultdict(list)
        for event in (
            MaintenanceDetail.objects.filter(
                asset_id__in=asset_ids,
                status="planned",
                deleted_at__isnull=True,
                event_start__gte=now,
            )
            .order_by("asset_id", "event_start")
        ):
            bucket = planned_by_asset[event.asset_id]
            if len(bucket) < NEXT_PLANNED_LIMIT:
                bucket.append(event)

        blockers_by_asset: dict[int, list[MaintenanceBlocker]] = defaultdict(list)
        for blocker in (
            MaintenanceBlocker.objects.filter(
                maintenance_detail__asset_id__in=asset_ids,
                maintenance_detail__deleted_at__isnull=True,
                end_date__isnull=True,
                deleted_at__isnull=True,
            )
            .select_related("maintenance_detail")
            .order_by("-start_date")
        ):
            blockers_by_asset[blocker.maintenance_detail.asset_id].append(blocker)

        limitations_by_asset: dict[int, list[AssetLimitationRecord]] = defaultdict(list)
        for record in (
            AssetLimitationRecord.objects.filter(
                maintenance_detail__asset_id__in=asset_ids,
                maintenance_detail__deleted_at__isnull=True,
                end_time__isnull=True,
                deleted_at__isnull=True,
            )
            .select_related("maintenance_detail")
            .order_by("-start_time")
        ):
            limitations_by_asset[record.maintenance_detail.asset_id].append(record)

        return [
            AssetMaintenanceDashboardStruct(
                asset=asset,
                next_planned_events=planned_by_asset.get(asset.pk, []),
                active_blockers=blockers_by_asset.get(asset.pk, []),
                active_limitation_records=limitations_by_asset.get(asset.pk, []),
            )
            for asset in assets
        ]
