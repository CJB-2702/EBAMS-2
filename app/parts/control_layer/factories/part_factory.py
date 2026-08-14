"""PartFactory — stateless creation of a Part root and its base revision.
No commit of its own beyond its single transaction.atomic()."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.errors import PartValidationError
from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.control_layer.guards.part_validator_guard import PartValidator
from app.parts.control_layer.managers.part_revision_manager import PartRevisionManager
from app.parts.control_layer.narrators.alias_narrator import AliasNarrator
from app.parts.control_layer.narrators.part_activity_narrator import PartActivityNarrator
from app.parts.models import AliasSource, Part, PartRevisionStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


# Re-exported for callers that historically imported it from this module.
__all__ = ["PartFactory", "PartValidationError"]


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
                # is_domain_limited starts False (model default) — it becomes True only
                # as a side effect of PartDomainManager.add_domain being called later.
                created_by=actor,
                updated_by=actor,
            )
            # Auto-create the base revision (major=1, minor=0, DRAFT — OQ3).
            PartRevisionManager(part, actor).release_major(
                summary="Initial revision",
                status=PartRevisionStatus.DRAFT,
            )

            # Alias hook (D8/D9): mirrors part_number into an INTERNAL alias.
            alias = AliasFactory.for_string(
                part,
                part.part_number,
                "INTERNAL",
                source=AliasSource.AUTO,
                actor=actor,
            )
            PartActivityNarrator.for_part(part, actor).record(
                AliasNarrator.alias_added(part, alias)
            )

        return part
