from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from app.events.control_layer.domain_structs.event_detail_struct import EventDetailStruct

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment, Event, File


class EventSuperStruct:
    """
    EventSuperStruct — data container for a list of Events and their complete child graphs.

    Status: placeholder. Built so the pattern exists when needed.

    Fetches all events, comments, attachments, and files in four queries across
    the entire batch, then distributes rows to EventDetailStruct.from_components
    for each event. Avoids the 4×N query cost of constructing EventDetailStruct
    per event in a loop.

    Relationships:
    Event[] (N)
        └── Comment (0..N per event)
            └── Attachment (0..N)
                    └── File (1 per attachment)

    Example query for from_components():
    events = list(Event.objects.select_related("domain", "created_by").filter(pk__in=event_ids))
    comments = list(
        Comment.objects.filter(activity_thread_id__in=event_ids, deleted_at__isnull=True)
        .select_related("created_by")
    )
    comment_ids = [c.pk for c in comments]
    attachments = list(
        Attachment.objects.filter(
            comment_id__in=comment_ids, deleted_at__isnull=True
        ).select_related("file")
    )
    files = [a.file for a in attachments]
    super_struct = EventSuperStruct.from_components(events, comments, attachments, files)
    """
    def __init__(self, event_ids: list[int]) -> None:
        from app.events.models import Attachment, Comment, Event

        # Query 1
        event_rows = list(
            Event.objects.select_related("domain", "created_by").filter(pk__in=event_ids)
        )

        # Query 2
        comment_rows = list(
            Comment.objects.filter(
                activity_thread_id__in=event_ids, deleted_at__isnull=True, is_human_made=True
            ).select_related("created_by")
        )

        comment_ids = [c.pk for c in comment_rows]

        # Query 3
        attachment_rows: list[Attachment] = []
        if comment_ids:
            attachment_rows = list(
                Attachment.objects.filter(
                    comment_id__in=comment_ids, deleted_at__isnull=True
                ).select_related("file")
            )

        # Query 4 — files already fetched via select_related
        file_rows = [a.file for a in attachment_rows]

        self.events: list[EventDetailStruct] = self._build_event_structs(
            event_rows, comment_rows, attachment_rows, file_rows
        )

    @classmethod
    def from_components(
        cls,
        event_rows: "list[Event]",
        comment_rows: "list[Comment]",
        attachment_rows: "list[Attachment]",
        file_rows: "list[File]",
    ) -> "EventSuperStruct":
        """Build from pre-fetched rows. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.events = cls._build_event_structs(
            event_rows, comment_rows, attachment_rows, file_rows
        )
        return instance

    @staticmethod
    def _build_event_structs(
        event_rows: "list[Event]",
        comment_rows: "list[Comment]",
        attachment_rows: "list[Attachment]",
        file_rows: "list[File]",
    ) -> "list[EventDetailStruct]":
        comments_by_event: dict[int, list] = defaultdict(list)
        for comment in comment_rows:
            comments_by_event[comment.activity_thread_id].append(comment)

        attachments_by_comment: dict[int, list] = defaultdict(list)
        for att in attachment_rows:
            attachments_by_comment[att.comment_id].append(att)

        event_structs = []
        for event in event_rows:
            evt_comments = comments_by_event.get(event.pk, [])
            evt_attachments = []
            for c in evt_comments:
                evt_attachments.extend(attachments_by_comment.get(c.pk, []))
            evt_files = [a.file for a in evt_attachments]
            event_structs.append(
                EventDetailStruct.from_components(event, evt_comments, evt_attachments, evt_files)
            )
        return event_structs

    def to_dict(self) -> list[dict]:
        return [e.to_dict() for e in self.events]
