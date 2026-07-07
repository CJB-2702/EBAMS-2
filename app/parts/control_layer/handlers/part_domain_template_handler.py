"""PartDomainTemplateHandler — issue/copy a whole domain set from a
DomainTemplate onto a Part (D14c). Mirrors the admin app's
DomainTemplate -> UserDomain rebase (TemplateDomainRebaseHandler). The
template is a source to copy from at apply time, not a stored FK — re-issuing
re-bases the Part's active mapping rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.administration.models import DomainTemplate, DomainTemplateItem
from app.parts.models import Part, PartDomainAccessMapping

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartDomainTemplateHandler:
    def __init__(self, part: Part, actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def apply(self, template_id: int) -> list[PartDomainAccessMapping]:
        template = DomainTemplate.objects.get(id=template_id)
        template_domain_ids = set(
            DomainTemplateItem.objects.filter(
                template=template, is_active=True
            ).values_list("domain_id", flat=True)
        )

        current = {
            m.domain_id: m
            for m in PartDomainAccessMapping.objects.filter(
                part=self.part, is_active=True
            )
        }

        to_deactivate = current.keys() - template_domain_ids
        if to_deactivate:
            PartDomainAccessMapping.objects.filter(
                part=self.part, domain_id__in=to_deactivate, is_active=True
            ).update(is_active=False, updated_by=self.actor)

        to_add = template_domain_ids - current.keys()
        for domain_id in to_add:
            PartDomainAccessMapping.objects.get_or_create(
                part=self.part,
                domain_id=domain_id,
                defaults={
                    "is_active": True,
                    "created_by": self.actor,
                    "updated_by": self.actor,
                },
            )

        return list(
            PartDomainAccessMapping.objects.filter(part=self.part, is_active=True)
        )
