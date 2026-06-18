"""ConfigurationTemplateManager — CRUD and revision management for ConfigurationTemplate.

Owns template creation/update/deactivation and the create_new_revision() clone
flow which produces a new template row from an existing one, copying all
TemplateModification and TemplateChild records, then deactivating the source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.configurations import ConfigurationTemplate, TemplateChild, TemplateModification

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel


class ConfigurationTemplateManager:
    """CRUD and revision lifecycle for ConfigurationTemplate records."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    # ── Create / update / deactivate ─────────────────────────────────────────

    def create(
        self,
        *,
        model: "AssetModel",
        name: str,
        revision: str | None = None,
        description: str | None = None,
    ) -> ConfigurationTemplate:
        name = name.strip()
        if not name:
            raise ValueError("Template name is required.")
        return ConfigurationTemplate.objects.create(
            model=model,
            name=name,
            revision=(revision or "").strip() or None,
            description=(description or "").strip() or None,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def update(
        self,
        template: ConfigurationTemplate,
        *,
        name: str | None = None,
        revision: str | None = None,
        description: str | None = None,
    ) -> ConfigurationTemplate:
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Template name cannot be blank.")
            template.name = name
        if revision is not None:
            template.revision = revision.strip() or None
        if description is not None:
            template.description = description.strip() or None
        template.updated_by = self.actor
        template.save()
        return template

    def deactivate(self, template: ConfigurationTemplate) -> ConfigurationTemplate:
        template.is_active = False
        template.updated_by = self.actor
        template.save()
        return template

    # ── Revision cloning ─────────────────────────────────────────────────────

    def create_new_revision(
        self, template: ConfigurationTemplate
    ) -> ConfigurationTemplate:
        """Clone template into a new revision, deactivate the source.

        Increments the minor part of a "major.minor" revision string.
        Copies all TemplateModification and TemplateChild rows verbatim.
        The old template is deactivated (is_active=False) atomically.
        """
        new_revision = self._next_revision(template.revision)

        new_template = ConfigurationTemplate.objects.create(
            model=template.model,
            name=template.name,
            revision=new_revision,
            description=template.description,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

        # Clone modification links.
        for tm in template.modification_links.all():
            TemplateModification.objects.create(
                template=new_template,
                defined_modification=tm.defined_modification,
                context_notes=tm.context_notes,
                is_required=tm.is_required,
                created_by=self.actor,
                updated_by=self.actor,
            )

        # Clone child declarations.
        for tc in template.child_declarations.all():
            TemplateChild.objects.create(
                parent_template=new_template,
                child_model=tc.child_model,
                quantity=tc.quantity,
                is_required=tc.is_required,
                created_by=self.actor,
                updated_by=self.actor,
            )

        # Deactivate the source revision.
        template.is_active = False
        template.updated_by = self.actor
        template.save()

        return new_template

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _next_revision(current: str | None) -> str:
        if not current:
            return "1.0"
        try:
            major, minor = current.split(".", 1)
            return f"{major}.{int(minor) + 1}"
        except (ValueError, AttributeError):
            return f"{current}.1"
