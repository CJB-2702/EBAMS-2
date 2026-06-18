"""TemplateModificationManager — manages TemplateModification and TemplateChild rows.

Handles the contents of a ConfigurationTemplate: which defined modifications
are expected (TemplateModification) and which child asset models are declared
(TemplateChild).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.configurations import (
    ConfigurationTemplate,
    DefinedModification,
    TemplateChild,
    TemplateModification,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel


class TemplateModificationManager:
    """Manages TemplateModification and TemplateChild records on a template."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    # ── TemplateModification operations ──────────────────────────────────────

    def add_modification(
        self,
        *,
        template: ConfigurationTemplate,
        defined_modification: DefinedModification,
        context_notes: str | None = None,
        is_required: bool = False,
    ) -> TemplateModification:
        if TemplateModification.objects.filter(
            template=template, defined_modification=defined_modification
        ).exists():
            raise ValueError(
                f"Modification '{defined_modification.name}' is already linked "
                f"to template '{template.name}'."
            )
        return TemplateModification.objects.create(
            template=template,
            defined_modification=defined_modification,
            context_notes=(context_notes or "").strip() or None,
            is_required=is_required,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def remove_modification(self, template_mod: TemplateModification) -> None:
        template_mod.delete()

    def set_modifications(
        self,
        *,
        template: ConfigurationTemplate,
        modification_ids: list[int],
    ) -> None:
        """Reconcile the template's required-modification set to ``modification_ids``.

        Hard create/delete (matching the other set-reconcile editors): adds the
        newly-selected modifications, drops the deselected ones, leaves the rest.
        """
        desired = set(modification_ids)
        existing = dict(
            TemplateModification.objects.filter(template=template).values_list(
                "defined_modification_id", "id"
            )
        )
        to_add = desired - existing.keys()
        to_remove_ids = [
            row_id for mod_id, row_id in existing.items() if mod_id not in desired
        ]
        for mod_id in to_add:
            TemplateModification.objects.create(
                template=template,
                defined_modification_id=mod_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
        if to_remove_ids:
            TemplateModification.objects.filter(id__in=to_remove_ids).delete()

    def update_modification(
        self,
        template_mod: TemplateModification,
        *,
        context_notes: str | None = None,
        is_required: bool | None = None,
    ) -> TemplateModification:
        if context_notes is not None:
            template_mod.context_notes = (context_notes or "").strip() or None
        if is_required is not None:
            template_mod.is_required = is_required
        template_mod.updated_by = self.actor
        template_mod.save()
        return template_mod

    # ── TemplateChild operations ──────────────────────────────────────────────

    def add_child(
        self,
        *,
        template: ConfigurationTemplate,
        child_model: "AssetModel",
        quantity: int = 1,
        is_required: bool = False,
    ) -> TemplateChild:
        # Prevent a template from declaring its own model as a child.
        if child_model_id := getattr(child_model, "pk", None):
            if child_model_id == template.model_id:
                raise ValueError(
                    "A template cannot declare its own model as an expected child."
                )
        return TemplateChild.objects.create(
            parent_template=template,
            child_model=child_model,
            quantity=max(1, quantity),
            is_required=is_required,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def remove_child(self, template_child: TemplateChild) -> None:
        template_child.delete()

    def update_child(
        self,
        template_child: TemplateChild,
        *,
        quantity: int | None = None,
        is_required: bool | None = None,
    ) -> TemplateChild:
        if quantity is not None:
            template_child.quantity = max(1, quantity)
        if is_required is not None:
            template_child.is_required = is_required
        template_child.updated_by = self.actor
        template_child.save()
        return template_child
