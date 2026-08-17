"""Struct: aggregated read model for a single Action.

Loads the action row plus its tool requirements and part-demand links in a
fixed number of queries, so MaintenanceContext / ActionContext callers never
grow ad-hoc query chains for the detail screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.maintenance.models.action import Action
from app.maintenance.models.action_tool import ActionTool
from app.maintenance.models.demand_link import MaintenanceDemandLink


@dataclass
class ActionStruct:
    action: Action
    action_tools: list[ActionTool] = field(default_factory=list)
    demand_links: list[MaintenanceDemandLink] = field(default_factory=list)

    @classmethod
    def load(cls, *, action_id: int) -> "ActionStruct":
        action = Action.objects.select_related(
            "event_detail", "assigned_user", "assigned_by", "completed_by"
        ).get(pk=action_id, deleted_at__isnull=True)
        action_tools = list(
            action.action_tools.filter(deleted_at__isnull=True)
            .select_related("tool")
            .order_by("sequence_order")
        )
        demand_links = list(
            action.demand_links.filter(deleted_at__isnull=True)
            .select_related("part_demand")
            .order_by("sequence_order")
        )
        return cls(action=action, action_tools=action_tools, demand_links=demand_links)

    @property
    def action_id(self) -> int:
        return self.action.pk

    @property
    def part_demands(self) -> list:
        return [link.part_demand for link in self.demand_links]

    def to_dict(self) -> dict:
        return {
            "id": self.action_id,
            "action_name": self.action.action_name,
            "status": self.action.status,
            "sequence_order": self.action.sequence_order,
            "event_detail_id": self.action.event_detail_id,
            "total_action_tools": len(self.action_tools),
            "total_part_demands": len(self.demand_links),
        }
