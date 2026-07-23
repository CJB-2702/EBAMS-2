"""PartImageNarrator — human-facing strings for Part gallery changes. Pure
string builder (Narrator): no DB access, no writes. PartImageManager posts
these as machine comments on the gallery thread it manages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import Attachment


class PartImageNarrator:
    @staticmethod
    def added(attachment: "Attachment") -> str:
        return f"Added image '{attachment.file.original_filename}' to the gallery."

    @staticmethod
    def removed(filename: str) -> str:
        return f"Removed image '{filename}' from the gallery."

    @staticmethod
    def primary_set(attachment: "Attachment") -> str:
        return f"Set primary image to '{attachment.file.original_filename}'."
