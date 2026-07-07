"""PartRevisionNarrator — human-readable revision/status strings. No writes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parts.models import Part, PartRevision


class PartRevisionNarrator:
    @staticmethod
    def major_released(part: "Part", rev: "PartRevision") -> str:
        return f"{part.part_number} rev {rev.major_revision_number} released"

    @staticmethod
    def redline_issued(part: "Part", rev: "PartRevision") -> str:
        return (
            f"{part.part_number} rev "
            f"{rev.major_revision_number}.{rev.minor_revision_number} redlined"
        )

    @staticmethod
    def status_changed(part: "Part", rev: "PartRevision", old: str, new: str) -> str:
        return (
            f"{part.part_number} rev "
            f"{rev.major_revision_number}.{rev.minor_revision_number}: {old} → {new}"
        )
