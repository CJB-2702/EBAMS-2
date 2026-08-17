"""Context: entry point for control logic around one TemplateActionSet id —
activation lifecycle and read-oriented statistics for the procedure template.
"""

from __future__ import annotations

from app.maintenance.models.templates.template_action_set import TemplateActionSet


class TemplateMaintenanceContext:
    def __init__(self, template_action_set_id: int) -> None:
        self.template_action_set_id = template_action_set_id
        self._template: TemplateActionSet | None = None

    @property
    def template_action_set(self) -> TemplateActionSet:
        if self._template is None:
            self._template = TemplateActionSet.objects.select_related(
                "asset_class", "asset_model", "domain"
            ).get(pk=self.template_action_set_id, deleted_at__isnull=True)
        return self._template

    def refresh(self) -> None:
        self._template = None

    @property
    def template_action_items(self):
        return self.template_action_set.template_action_items.filter(
            deleted_at__isnull=True
        ).order_by("sequence_order")

    @property
    def total_action_items(self) -> int:
        return self.template_action_items.count()

    @property
    def total_estimated_duration_minutes(self) -> int:
        return sum(
            item.estimated_duration_minutes or 0 for item in self.template_action_items
        )

    def get_part_demands_by_action(self) -> dict[int, list]:
        return {
            item.pk: list(item.template_part_demands.filter(deleted_at__isnull=True))
            for item in self.template_action_items
        }

    def get_tools_by_action(self) -> dict[int, list]:
        return {
            item.pk: list(item.template_action_tools.filter(deleted_at__isnull=True))
            for item in self.template_action_items
        }

    def activate(self, *, actor=None) -> TemplateActionSet:
        template = self.template_action_set
        template.is_active = True
        template.updated_by = actor
        template.save(update_fields=["is_active", "updated_by", "updated_at"])
        self.refresh()
        return template

    def deactivate(self, *, actor=None) -> TemplateActionSet:
        template = self.template_action_set
        template.is_active = False
        template.updated_by = actor
        template.save(update_fields=["is_active", "updated_by", "updated_at"])
        self.refresh()
        return template

    def to_dict(self) -> dict:
        template = self.template_action_set
        return {
            "id": self.template_action_set_id,
            "task_name": template.task_name,
            "description": template.description,
            "revision": template.revision,
            "is_active": template.is_active,
            "total_action_items": self.total_action_items,
            "total_estimated_duration_minutes": self.total_estimated_duration_minutes,
        }
