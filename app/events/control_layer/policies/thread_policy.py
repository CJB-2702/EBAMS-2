"""ThreadPolicy — capability guard for activity thread rows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.events.models.event import ActivityThreadType

if TYPE_CHECKING:
    from app.events.models import Event


class ThreadPolicy:
    """
    Pure-read policy: inspects thread flags and answers capability questions.
    No DB writes.
    """

    def __init__(self, row: "Event") -> None:
        self._row = row

    def can_add_comment(self) -> bool:
        return self._row.allow_comments

    def can_attach_directly(self) -> bool:
        return self._row.allow_direct_attachments

    def can_attach_to_comment(self) -> bool:
        return self._row.allow_comments

    def is_event_row(self) -> bool:
        return self._row.thread_type == ActivityThreadType.EVENT
