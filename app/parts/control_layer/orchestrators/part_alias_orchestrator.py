"""PartAliasOrchestrator — fills the Phase 1 create hook (D8). Runs inside the
same transaction as PartFactory.create so the index can never drift."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.control_layer.managers.part_activity_manager import PartActivityManager
from app.parts.control_layer.narrators.alias_narrator import AliasNarrator
from app.parts.models import AliasSource

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Alias, Part


class PartAliasOrchestrator:
    @staticmethod
    def on_part_created(part: "Part", actor: "AbstractUser | None") -> "Alias":
        alias = AliasFactory.for_string(
            part,
            part.part_number,
            "INTERNAL",
            source=AliasSource.AUTO,
            actor=actor,
        )
        PartActivityManager.for_part(part, actor).record(
            AliasNarrator.alias_added(part, alias)
        )
        return alias
