"""Struct: aggregated read model for one template lineage — the lineage row
plus its revision history, newest first. The head revision's manifest is
loaded separately (it is the expensive part and most screens only need the
lineage summary plus a revision list)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dispatching.models.templates.dispatch_template import DispatchTemplate
from app.dispatching.models.templates.dispatch_template_revision import (
    DispatchTemplateRevision,
)


@dataclass
class TemplateLineageStruct:
    template: DispatchTemplate
    revisions: list[DispatchTemplateRevision] = field(default_factory=list)

    @classmethod
    def load(cls, *, template_id: int) -> "TemplateLineageStruct":
        template = DispatchTemplate.objects.select_related(
            "domain", "head_revision", "copied_from_revision"
        ).get(pk=template_id)
        revisions = list(
            template.revisions.select_related("created_by").order_by("-revision_number")
        )
        return cls(template=template, revisions=revisions)

    @property
    def template_id(self) -> int:
        return self.template.pk

    @property
    def head_revision(self) -> DispatchTemplateRevision | None:
        return self.template.head_revision

    def to_dict(self) -> dict:
        return {
            "id": self.template_id,
            "domain_id": self.template.domain_id,
            "head_revision_id": self.template.head_revision_id,
            "head_title": self.head_revision.title if self.head_revision else None,
            "is_retired": self.template.is_retired,
            "revision_count": len(self.revisions),
        }
