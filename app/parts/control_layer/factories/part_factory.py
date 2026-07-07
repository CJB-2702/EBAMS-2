"""PartFactory — stateless creation of a Part root and its base revision.
No commit of its own beyond its single transaction.atomic()."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.guards.part_validator_guard import PartValidator
from app.parts.control_layer.managers.part_revision_manager import PartRevisionManager
from app.parts.models import Part, PartRevisionStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class PartFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> Part:
        errors = PartValidator.check(part_number=data.get("part_number", ""))
        if errors:
            raise PartValidationError(errors)

        with transaction.atomic():
            part = Part.objects.create(
                part_number=data["part_number"].strip(),
                name=(data.get("name") or "").strip(),
                description=data.get("description") or "",
                part_type=data.get("part_type") or "",
                category=data.get("category") or "",
                is_active=data.get("is_active", True),
                is_domain_limited=data.get("is_domain_limited", False),
                created_by=actor,
                updated_by=actor,
            )
            # Auto-create the base revision (major=1, minor=0, DRAFT — OQ3).
            PartRevisionManager(part, actor).release_major(
                summary="Initial revision",
                status=PartRevisionStatus.DRAFT,
            )

            # Alias hook (D8/D9): mirrors part_number into an INTERNAL alias.
            from app.parts.control_layer.orchestrators.part_alias_orchestrator import (
                PartAliasOrchestrator,
            )

            PartAliasOrchestrator.on_part_created(part, actor)

        return part
