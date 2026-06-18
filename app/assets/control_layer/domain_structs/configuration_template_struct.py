"""ConfigurationTemplateStruct — read model for a ConfigurationTemplate.

Loads the template with its TemplateModification links (resolved to
DefinedModification) and its TemplateChild declarations (resolved to
AssetModel) in one pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.configurations import (
    ConfigurationTemplate,
    TemplateChild,
    TemplateModification,
)

if TYPE_CHECKING:
    pass


class ConfigurationTemplateStruct:
    """Read model for a single ConfigurationTemplate."""

    def __init__(
        self,
        template: ConfigurationTemplate,
        modifications: list[TemplateModification],
        children: list[TemplateChild],
    ) -> None:
        self.template = template
        self.modifications = modifications
        self.children = children

    @classmethod
    def from_template(cls, template: ConfigurationTemplate) -> "ConfigurationTemplateStruct":
        modifications = list(
            template.modification_links
            .select_related("defined_modification")
            .order_by("id")
        )
        children = list(
            template.child_declarations
            .select_related("child_model")
            .order_by("id")
        )
        return cls(template=template, modifications=modifications, children=children)

    @classmethod
    def from_id(cls, template_id: int) -> "ConfigurationTemplateStruct | None":
        try:
            template = (
                ConfigurationTemplate.objects.select_related("model")
                .get(pk=template_id)
            )
        except ConfigurationTemplate.DoesNotExist:
            return None
        return cls.from_template(template)

    # ── Convenience filters ──────────────────────────────────────────────────

    def get_required_modifications(self) -> list[TemplateModification]:
        return [m for m in self.modifications if m.is_required]

    def get_optional_modifications(self) -> list[TemplateModification]:
        return [m for m in self.modifications if not m.is_required]

    def get_required_children(self) -> list[TemplateChild]:
        return [c for c in self.children if c.is_required]

    def get_optional_children(self) -> list[TemplateChild]:
        return [c for c in self.children if not c.is_required]

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "template": {
                "id": self.template.pk,
                "name": self.template.name,
                "revision": self.template.revision,
                "description": self.template.description,
                "is_active": self.template.is_active,
                "model_id": self.template.model_id,
            },
            "modifications": [
                {
                    "id": m.pk,
                    "defined_modification_id": m.defined_modification_id,
                    "name": m.defined_modification.name if m.defined_modification else None,
                    "code": m.defined_modification.code if m.defined_modification else None,
                    "category": m.defined_modification.category if m.defined_modification else None,
                    "context_notes": m.context_notes,
                    "is_required": m.is_required,
                }
                for m in self.modifications
            ],
            "children": [
                {
                    "id": c.pk,
                    "child_model_id": c.child_model_id,
                    "child_model_name": str(c.child_model) if c.child_model else None,
                    "quantity": c.quantity,
                    "is_required": c.is_required,
                }
                for c in self.children
            ],
        }
