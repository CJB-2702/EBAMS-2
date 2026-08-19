"""Manager: creates and removes ActionTool rows (tool requirements) for a live
Action step. Supports both a catalog parts.Tool reference and an ad-hoc
tool_name — mirrors AbstractActionTool's own either/or shape."""

from __future__ import annotations

from django.utils import timezone

from app.maintenance.models.action import Action
from app.maintenance.models.action_tool import ActionTool


class ActionToolManager:
    @classmethod
    def create_for_action(
        cls,
        *,
        action_id: int,
        tool_id: int | None = None,
        tool_name: str = "",
        quantity_required: int = 1,
        specifications: str = "",
        notes: str = "",
        is_required: bool = True,
        sequence_order: int | None = None,
        actor=None,
    ) -> ActionTool:
        if not tool_id and not tool_name:
            raise ValueError("Either tool_id (catalog) or tool_name (ad-hoc) is required.")
        action = Action.objects.get(pk=action_id, deleted_at__isnull=True)
        if sequence_order is None:
            sequence_order = (
                action.action_tools.filter(deleted_at__isnull=True).count() + 1
            )
        return ActionTool.objects.create(
            action=action,
            tool_id=tool_id,
            tool_name=tool_name,
            quantity_required=quantity_required,
            specifications=specifications,
            notes=notes,
            is_required=is_required,
            sequence_order=sequence_order,
            created_by=actor,
            updated_by=actor,
        )

    @classmethod
    def update(cls, *, action_tool_id: int, actor=None, **fields) -> ActionTool:
        tool = ActionTool.objects.get(pk=action_tool_id, deleted_at__isnull=True)
        update_fields: list[str] = []
        for field_name in (
            "tool_id", "tool_name", "quantity_required", "specifications", "notes",
        ):
            if field_name in fields and fields[field_name] is not None:
                setattr(tool, field_name, fields[field_name])
                update_fields.append(field_name)
        if update_fields:
            tool.updated_by = actor
            update_fields += ["updated_by", "updated_at"]
            tool.save(update_fields=update_fields)
        return tool

    @classmethod
    def delete(cls, *, action_tool_id: int, actor=None) -> None:
        ActionTool.objects.filter(pk=action_tool_id).update(
            deleted_at=timezone.now(), updated_by=actor
        )
