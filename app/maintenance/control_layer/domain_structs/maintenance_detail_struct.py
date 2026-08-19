"""Struct: aggregated read model for a single MaintenanceDetail event.

Loads the event row plus its actions, blockers, and asset limitation records —
the three child collections R4's completion truth table checks — in a fixed
number of queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.events.models.details.maintenance import MaintenanceDetail
from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.asset_limitation import AssetLimitationRecord
from app.maintenance.models.blocker import MaintenanceBlocker


@dataclass
class MaintenanceDetailStruct:
    maintenance_detail: MaintenanceDetail
    actions: list[Action] = field(default_factory=list)
    blockers: list[MaintenanceBlocker] = field(default_factory=list)
    limitation_records: list[AssetLimitationRecord] = field(default_factory=list)

    @classmethod
    def load(cls, *, maintenance_detail_id: int) -> "MaintenanceDetailStruct":
        maintenance_detail = MaintenanceDetail.objects.select_related(
            "domain", "asset", "assigned_user", "template_action_set"
        ).get(pk=maintenance_detail_id, deleted_at__isnull=True)
        actions = list(
            maintenance_detail.actions.filter(deleted_at__isnull=True)
            .select_related("assigned_user")
            .order_by("sequence_order")
        )
        blockers = list(
            maintenance_detail.blockers.filter(deleted_at__isnull=True).order_by(
                "-start_date"
            )
        )
        limitation_records = list(
            maintenance_detail.limitation_records.filter(
                deleted_at__isnull=True
            ).order_by("-start_time")
        )
        return cls(
            maintenance_detail=maintenance_detail,
            actions=actions,
            blockers=blockers,
            limitation_records=limitation_records,
        )

    @property
    def maintenance_detail_id(self) -> int:
        return self.maintenance_detail.pk

    @property
    def active_blockers(self) -> list[MaintenanceBlocker]:
        return [b for b in self.blockers if b.end_date is None]

    @property
    def active_limitation_records(self) -> list[AssetLimitationRecord]:
        return [r for r in self.limitation_records if r.end_time is None]

    @property
    def completed_actions(self) -> list[Action]:
        return [a for a in self.actions if a.status == ActionStatus.COMPLETE]

    def to_dict(self) -> dict:
        return {
            "id": self.maintenance_detail_id,
            "title": self.maintenance_detail.title,
            "status": self.maintenance_detail.status,
            "asset_id": self.maintenance_detail.asset_id,
            "total_actions": len(self.actions),
            "completed_actions": len(self.completed_actions),
            "total_blockers": len(self.blockers),
            "active_blockers": len(self.active_blockers),
            "active_limitation_records": len(self.active_limitation_records),
        }
