"""Context: entry point for control logic around one template lineage id.

Editing itself is not a verb here — it happens entirely in
TemplateDraftSessionAdapter, which touches no database rows until commit.
This Context is the read façade plus the two lineage-wide verbs: retire and
reinstate."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.dispatching.control_layer.domain_structs.template_lineage_struct import (
    TemplateLineageStruct,
)
from app.dispatching.models.templates.dispatch_template import DispatchTemplate

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class TemplateContext:
    def __init__(self, template_id: int, actor: "AbstractUser") -> None:
        self.actor = actor
        self.struct = TemplateLineageStruct.load(template_id=template_id)

    @classmethod
    def from_struct(cls, struct: TemplateLineageStruct, actor: "AbstractUser") -> "TemplateContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        return ctx

    @property
    def template(self) -> DispatchTemplate:
        return self.struct.template

    def refresh(self) -> None:
        self.struct = TemplateLineageStruct.load(template_id=self.template.pk)

    def retire(self, *, reason: str) -> DispatchTemplate:
        from app.dispatching.control_layer.managers.template_retirement_manager import (
            TemplateRetirementManager,
        )

        result = TemplateRetirementManager.retire(
            template_id=self.template.pk, reason=reason, actor=self.actor
        )
        self.refresh()
        return result

    def reinstate(self) -> DispatchTemplate:
        from app.dispatching.control_layer.managers.template_retirement_manager import (
            TemplateRetirementManager,
        )

        result = TemplateRetirementManager.reinstate(template_id=self.template.pk, actor=self.actor)
        self.refresh()
        return result
