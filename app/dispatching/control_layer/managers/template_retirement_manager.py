"""Manager: retiring/reinstating a template lineage. Lineage-wide, requires
a reason, reversible (dispatching_starter_kit/1_dispatch_templates.md §5,
R10). Never touches a revision — retirement is a lineage fact."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.dispatching.models.templates.dispatch_template import DispatchTemplate

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class TemplateRetirementManager:
    @classmethod
    def retire(cls, *, template_id: int, reason: str, actor: "AbstractUser") -> DispatchTemplate:
        if not (reason or "").strip():
            raise ValueError("A reason is required to retire a template.")
        template = DispatchTemplate.objects.get(pk=template_id)
        with transaction.atomic():
            template.is_retired = True
            template.retired_reason = reason
            template.retired_by = actor
            template.retired_at = timezone.now()
            template.updated_by = actor
            template.save()
        return template

    @classmethod
    def reinstate(cls, *, template_id: int, actor: "AbstractUser") -> DispatchTemplate:
        template = DispatchTemplate.objects.get(pk=template_id)
        with transaction.atomic():
            template.is_retired = False
            template.retired_reason = ""
            template.retired_by = None
            template.retired_at = None
            template.updated_by = actor
            template.save()
        return template
