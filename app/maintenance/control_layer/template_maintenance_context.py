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
                "asset_class", "domain"
            ).prefetch_related("asset_models").get(
                pk=self.template_action_set_id, deleted_at__isnull=True
            )
        return self._template

    def refresh(self) -> None:
        self._template = None

    @property
    def template_action_items(self):
        return self.template_action_set.template_action_items.filter(
            deleted_at__isnull=True
        ).order_by("sequence_order")

    @property
    def asset_models(self):
        return self.template_action_set.asset_models.all().order_by(
            "model_name", "version_rank", "version"
        )

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

    @property
    def all_parts_required(self) -> list[tuple]:
        """Flat roll-up of every step's parts, each paired with its owning
        action name."""
        part_demands_by_action = self.get_part_demands_by_action()
        items_by_pk = {item.pk: item for item in self.template_action_items}
        pairs = []
        for item_pk, demands in part_demands_by_action.items():
            action_name = items_by_pk[item_pk].action_name
            for demand in demands:
                pairs.append((demand, action_name))
        return pairs

    @property
    def all_tools_required(self) -> list[tuple]:
        """Flat roll-up of every step's tools, each paired with its owning
        action name — the legacy page names the step next to the tool so a
        reader can see which step needs it."""
        tools_by_action = self.get_tools_by_action()
        items_by_pk = {item.pk: item for item in self.template_action_items}
        pairs = []
        for item_pk, tools in tools_by_action.items():
            action_name = items_by_pk[item_pk].action_name
            for tool in tools:
                pairs.append((tool, action_name))
        return pairs

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

    def add_asset_models(self, model_ids, *, actor=None) -> None:
        self.template_action_set.asset_models.add(*model_ids)
        self.refresh()

    @property
    def is_newest_revision(self) -> bool:
        return not self.template_action_set.subsequent_revisions.filter(
            deleted_at__isnull=True
        ).exists()

    @property
    def revision_chain(self) -> list[TemplateActionSet]:
        """Every template in this one's lineage, oldest first, current one
        included — walked via prior_revision backward and
        subsequent_revisions forward."""
        current = self.template_action_set
        older = []
        cursor = current.prior_revision
        while cursor is not None:
            older.append(cursor)
            cursor = cursor.prior_revision
        older.reverse()

        newer = []
        cursor = current.subsequent_revisions.filter(deleted_at__isnull=True).first()
        while cursor is not None:
            newer.append(cursor)
            cursor = cursor.subsequent_revisions.filter(deleted_at__isnull=True).first()

        return [*older, current, *newer]

    def remove_asset_models(self, model_ids, *, actor=None) -> None:
        self.template_action_set.asset_models.remove(*model_ids)
        self.refresh()

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
