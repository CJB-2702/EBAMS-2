"""PartAliasOrchestrator — fills the Phase 1 create hook (D8). Runs inside the
same transaction as PartFactory.create so the index can never drift."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.models import AliasSource

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Alias, Part


class PartAliasOrchestrator:
    @staticmethod
    def on_part_created(part: "Part", actor: "AbstractUser | None") -> "Alias":
        return AliasFactory.for_string(
            part,
            part.part_number,
            "INTERNAL",
            source=AliasSource.AUTO,
            actor=actor,
        )
