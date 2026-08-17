"""Factory: expands TemplateActionItem / ProtoActionItem rows into live Action
steps (+ ActionTool rows, + PartDemand via MaintenanceDemandLink) inside one
atomic transaction per R2 — a template-instantiation cascade either fully
lands or fully rolls back.
"""

from __future__ import annotations

from django.db import transaction

from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.action_tool import ActionTool
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.models.templates.template_action_item import TemplateActionItem


class ActionFactory:
    @classmethod
    def create_from_template_action_item(
        cls,
        *,
        template_action_item_id: int,
        maintenance_detail_id: int,
        sequence_order: int | None = None,
        copy_part_demands: bool = True,
        copy_tools: bool = True,
        actor=None,
        commit: bool = True,
    ) -> Action:
        template_item = TemplateActionItem.objects.get(
            pk=template_action_item_id, deleted_at__isnull=True
        )

        def _create() -> Action:
            action = Action.objects.create(
                event_detail_id=maintenance_detail_id,
                template_action_item=template_item,
                sequence_order=sequence_order or template_item.sequence_order,
                action_name=template_item.action_name,
                description=template_item.description,
                instructions=template_item.instructions,
                estimated_duration_minutes=template_item.estimated_duration_minutes,
                safety_notes=template_item.safety_notes,
                notes=template_item.notes,
                status=ActionStatus.NOT_STARTED,
                created_by=actor,
                updated_by=actor,
            )
            if copy_tools:
                for template_tool in template_item.template_action_tools.filter(
                    deleted_at__isnull=True
                ):
                    ActionTool.objects.create(
                        action=action,
                        tool_id=template_tool.tool_id,
                        tool_name=template_tool.tool_name,
                        quantity_required=template_tool.quantity_required,
                        specifications=template_tool.specifications,
                        notes=template_tool.notes,
                        is_required=template_tool.is_required,
                        sequence_order=template_tool.sequence_order,
                        created_by=actor,
                        updated_by=actor,
                    )
            if copy_part_demands:
                for template_demand in template_item.template_part_demands.filter(
                    deleted_at__isnull=True
                ):
                    PartDemandManager.create_for_action(
                        action_id=action.pk,
                        part_id=template_demand.part_id,
                        quantity_requested=template_demand.quantity_required,
                        notes=template_demand.notes,
                        actor=actor,
                    )
            return action

        if commit:
            with transaction.atomic():
                return _create()
        return _create()

    @classmethod
    def create_from_template_action_set(
        cls,
        *,
        template_action_set_id: int,
        maintenance_detail_id: int,
        actor=None,
        commit: bool = True,
    ) -> list[Action]:
        from app.maintenance.models.templates.template_action_set import TemplateActionSet

        template_set = TemplateActionSet.objects.get(
            pk=template_action_set_id, deleted_at__isnull=True
        )
        items = template_set.template_action_items.filter(
            deleted_at__isnull=True
        ).order_by("sequence_order")

        def _create() -> list[Action]:
            return [
                cls.create_from_template_action_item(
                    template_action_item_id=item.pk,
                    maintenance_detail_id=maintenance_detail_id,
                    actor=actor,
                    commit=False,
                )
                for item in items
            ]

        if commit:
            with transaction.atomic():
                return _create()
        return _create()

    @classmethod
    def create_from_proto_action_item(
        cls,
        *,
        proto_action_item_id: int,
        maintenance_detail_id: int,
        sequence_order: int,
        copy_part_demands: bool = True,
        copy_tools: bool = True,
        actor=None,
        commit: bool = True,
    ) -> Action:
        proto_item = ProtoActionItem.objects.get(
            pk=proto_action_item_id, deleted_at__isnull=True
        )

        def _create() -> Action:
            action = Action.objects.create(
                event_detail_id=maintenance_detail_id,
                sequence_order=sequence_order,
                action_name=proto_item.action_name,
                description=proto_item.description,
                instructions=proto_item.instructions,
                estimated_duration_minutes=proto_item.estimated_duration_minutes,
                safety_notes=proto_item.safety_notes,
                notes=proto_item.notes,
                status=ActionStatus.NOT_STARTED,
                created_by=actor,
                updated_by=actor,
            )
            if copy_tools:
                for proto_tool in proto_item.proto_action_tools.filter(
                    deleted_at__isnull=True
                ):
                    ActionTool.objects.create(
                        action=action,
                        tool_id=proto_tool.tool_id,
                        tool_name=proto_tool.tool_name,
                        quantity_required=proto_tool.quantity_required,
                        specifications=proto_tool.specifications,
                        notes=proto_tool.notes,
                        is_required=proto_tool.is_required,
                        sequence_order=proto_tool.sequence_order,
                        created_by=actor,
                        updated_by=actor,
                    )
            if copy_part_demands:
                for proto_demand in proto_item.proto_part_demands.filter(
                    deleted_at__isnull=True
                ):
                    PartDemandManager.create_for_action(
                        action_id=action.pk,
                        part_id=proto_demand.part_id,
                        quantity_requested=proto_demand.quantity_required,
                        notes=proto_demand.notes,
                        actor=actor,
                    )
            return action

        if commit:
            with transaction.atomic():
                return _create()
        return _create()
