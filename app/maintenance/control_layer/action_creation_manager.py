"""Manager: creates Action rows for a MaintenanceContext — blank, from a proto
library item, from a template item, or duplicated from a sibling — with
correct sequence-order insertion and shifting of the rest of the list.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import F

from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.action_tool import ActionTool


class ActionCreationManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    def _shift_for_insertion(self, *, insert_position: str, after_action_id: int | None) -> int:
        actions = self._ctx.struct.actions
        if insert_position not in ("end", "beginning", "after"):
            raise ValueError(f"Invalid insert_position: {insert_position}")
        if not actions:
            return 1

        if insert_position == "end":
            return max(a.sequence_order for a in actions) + 1

        if insert_position == "beginning":
            Action.objects.filter(
                event_detail_id=self._ctx.maintenance_detail_id, deleted_at__isnull=True
            ).update(sequence_order=F("sequence_order") + 1)
            return 1

        if not after_action_id:
            raise ValueError("after_action_id required when insert_position is 'after'.")
        target = next((a for a in actions if a.pk == after_action_id), None)
        if target is None:
            raise ValueError(f"Action {after_action_id} not found in this event.")
        Action.objects.filter(
            event_detail_id=self._ctx.maintenance_detail_id,
            deleted_at__isnull=True,
            sequence_order__gt=target.sequence_order,
        ).update(sequence_order=F("sequence_order") + 1)
        return target.sequence_order + 1

    def create_blank(
        self,
        *,
        action_name: str,
        description: str = "",
        instructions: str = "",
        estimated_duration_minutes: int | None = None,
        safety_notes: str = "",
        notes: str = "",
        insert_position: str = "end",
        after_action_id: int | None = None,
        actor=None,
    ) -> Action:
        with transaction.atomic():
            seq = self._shift_for_insertion(
                insert_position=insert_position, after_action_id=after_action_id
            )
            action = Action.objects.create(
                event_detail_id=self._ctx.maintenance_detail_id,
                sequence_order=seq,
                action_name=action_name,
                description=description,
                instructions=instructions,
                estimated_duration_minutes=estimated_duration_minutes,
                safety_notes=safety_notes,
                notes=notes,
                status=ActionStatus.NOT_STARTED,
                created_by=actor,
                updated_by=actor,
            )
        self._ctx.refresh()
        return action

    def create_from_proto_action_item(
        self,
        *,
        proto_action_item_id: int,
        insert_position: str = "end",
        after_action_id: int | None = None,
        copy_part_demands: bool = False,
        copy_tools: bool = False,
        actor=None,
    ) -> Action:
        from app.maintenance.control_layer.action_factory import ActionFactory

        with transaction.atomic():
            seq = self._shift_for_insertion(
                insert_position=insert_position, after_action_id=after_action_id
            )
            action = ActionFactory.create_from_proto_action_item(
                proto_action_item_id=proto_action_item_id,
                maintenance_detail_id=self._ctx.maintenance_detail_id,
                sequence_order=seq,
                copy_part_demands=copy_part_demands,
                copy_tools=copy_tools,
                actor=actor,
                commit=False,
            )
        self._ctx.refresh()
        return action

    def create_from_template_action_item(
        self,
        *,
        template_action_item_id: int,
        insert_position: str = "end",
        after_action_id: int | None = None,
        copy_part_demands: bool = True,
        copy_tools: bool = True,
        actor=None,
    ) -> Action:
        from app.maintenance.control_layer.action_factory import ActionFactory

        with transaction.atomic():
            seq = self._shift_for_insertion(
                insert_position=insert_position, after_action_id=after_action_id
            )
            action = ActionFactory.create_from_template_action_item(
                template_action_item_id=template_action_item_id,
                maintenance_detail_id=self._ctx.maintenance_detail_id,
                sequence_order=seq,
                copy_part_demands=copy_part_demands,
                copy_tools=copy_tools,
                actor=actor,
                commit=False,
            )
        self._ctx.refresh()
        return action

    def duplicate(
        self,
        *,
        source_action_id: int,
        insert_position: str = "end",
        after_action_id: int | None = None,
        copy_part_demands: bool = False,
        copy_tools: bool = False,
        actor=None,
    ) -> Action:
        source = Action.objects.get(
            pk=source_action_id, event_detail_id=self._ctx.maintenance_detail_id
        )
        with transaction.atomic():
            seq = self._shift_for_insertion(
                insert_position=insert_position, after_action_id=after_action_id
            )
            action = Action.objects.create(
                event_detail_id=self._ctx.maintenance_detail_id,
                template_action_item_id=source.template_action_item_id,
                sequence_order=seq,
                action_name=source.action_name,
                description=source.description,
                instructions=source.instructions,
                estimated_duration_minutes=source.estimated_duration_minutes,
                safety_notes=source.safety_notes,
                notes=source.notes,
                status=ActionStatus.NOT_STARTED,
                created_by=actor,
                updated_by=actor,
            )
            if copy_tools:
                for tool in source.action_tools.filter(deleted_at__isnull=True):
                    ActionTool.objects.create(
                        action=action,
                        tool_id=tool.tool_id,
                        tool_name=tool.tool_name,
                        quantity_required=tool.quantity_required,
                        specifications=tool.specifications,
                        notes=tool.notes,
                        is_required=tool.is_required,
                        sequence_order=tool.sequence_order,
                        created_by=actor,
                        updated_by=actor,
                    )
            if copy_part_demands:
                from app.maintenance.control_layer.part_demand_manager import (
                    PartDemandManager,
                )

                for link in source.demand_links.filter(deleted_at__isnull=True):
                    PartDemandManager.create_for_action(
                        action_id=action.pk,
                        part_id=link.part_demand.part_id,
                        quantity_requested=link.part_demand.quantity_requested,
                        notes=f"Duplicated from action #{source.pk}.",
                        actor=actor,
                    )
        self._ctx.refresh()
        return action
