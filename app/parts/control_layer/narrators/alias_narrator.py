"""AliasNarrator — human-readable alias strings for the Part audit feed. No writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parts.models import Alias, Part


class AliasNarrator:
    @staticmethod
    def alias_added(part: "Part", alias: "Alias") -> str:
        return f"Alias {alias.alias} ({alias.alias_type}) added to {part.part_number}"
