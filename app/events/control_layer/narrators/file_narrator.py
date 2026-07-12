"""FileNarrator — human-facing strings for file attach/detach timeline events.

Pure string builder (Narrator): no DB access, no writes. DirectAttachmentHandler
posts these as machine comments on threads that opt into file-change narration.
The short id disambiguates identical filenames without dumping a full UUID into
the human-facing timeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import File

_UUID_PREVIEW_LEN = 6


def _short_id(file: "File") -> str:
    return f"{str(file.id)[:_UUID_PREVIEW_LEN]}…"


class FileNarrator:
    @staticmethod
    def attached(file: "File") -> str:
        return f"Attached {file.original_filename} ({_short_id(file)})"

    @staticmethod
    def removed(file: "File") -> str:
        return f"Removed {file.original_filename} ({_short_id(file)})"
