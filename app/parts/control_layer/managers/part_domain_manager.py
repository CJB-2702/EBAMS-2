"""PartDomainManager — the only writer of PartDomainAccessMapping rows and of
Part.is_domain_limited (D14). Reuses administration.Domain; adds no domain table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.administration.models import Domain
from app.parts.models import Part, PartDomainAccessMapping

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartDomainManager:
    def __init__(self, part: Part, actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def set_limited(self, flag: bool) -> Part:
        self.part.is_domain_limited = flag
        self.part.updated_by = self.actor
        self.part.save(update_fields=["is_domain_limited", "updated_at", "updated_by"])
        return self.part

    def add_domain(self, domain_id: int) -> PartDomainAccessMapping:
        mapping, created = PartDomainAccessMapping.objects.get_or_create(
            part=self.part,
            domain_id=domain_id,
            defaults={
                "is_active": True,
                "created_by": self.actor,
                "updated_by": self.actor,
            },
        )
        if not created and not mapping.is_active:
            mapping.is_active = True
            mapping.updated_by = self.actor
            mapping.save(update_fields=["is_active", "updated_at", "updated_by"])
        if not self.part.is_domain_limited:
            self.set_limited(True)
        return mapping

    def remove_domain(self, domain_id: int) -> None:
        PartDomainAccessMapping.objects.filter(
            part=self.part, domain_id=domain_id, is_active=True
        ).update(is_active=False, updated_by=self.actor)
        if self.part.is_domain_limited and not self._has_active_mappings():
            self.set_limited(False)

    def make_global(self) -> None:
        """Explicit 'remove all domain assignments' action — clears every active
        mapping and flips is_domain_limited off in one pass (D14: default is
        global when no assignments exist)."""
        PartDomainAccessMapping.objects.filter(part=self.part, is_active=True).update(
            is_active=False, updated_by=self.actor
        )
        self.set_limited(False)

    def _has_active_mappings(self) -> bool:
        return PartDomainAccessMapping.objects.filter(
            part=self.part, is_active=True
        ).exists()

    def domains(self) -> list[Domain]:
        return list(
            Domain.objects.filter(
                part_domain_access_mappings__part=self.part,
                part_domain_access_mappings__is_active=True,
            )
        )
