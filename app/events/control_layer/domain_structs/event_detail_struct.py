from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from django.db.models import Prefetch

from app.events.control_layer.domain_structs.comment_struct import CommentStruct

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment, Event, File


class EventDetailStruct:
    """
    EventDetailStruct — data container for a single Event and its entire child graph.

    Loads the event, all of its comments, and all attachments (comment-linked +
    standalone) in exactly 3 SQL queries:
    1. Event row (+ domain, created_by via JOIN)
    2. All comments for that event (+ created_by via JOIN)
    3. All active attachments for that event by event_id (+ file via JOIN)

    Attachments are partitioned in Python after the third query:
      comment_id non-null → distributed into the matching CommentStruct
      comment_id null     → collected in self.standalone_attachments

    Relationships:
    Event (1)
        ├── Comment (0..N)   related_name="comments"
        │     └── Attachment (0..N, comment_id non-null)
        │             └── File (1 per attachment)
        └── Attachment (0..N, comment_id null — standalone)
                └── File (1 per attachment)
    """
    def __init__(self, event_id: int, include_shadow_comments: bool = False) -> None:
        from app.events.models import Attachment, Comment, Event

        comment_qs = Comment.objects.filter(deleted_at__isnull=True).select_related("created_by")
        if not include_shadow_comments:
            comment_qs = comment_qs.filter(is_human_made=True)

        # Query 1+2: event + comments prefetch (Event.threads resolves any thread type)
        event = (
            Event.threads.select_related("domain", "created_by")
            .prefetch_related(Prefetch("comments", queryset=comment_qs, to_attr="loaded_comments"))
            .get(pk=event_id)
        )

        # Query 3: all active attachments for this thread in one shot
        all_attachments = list(
            Attachment.objects.filter(
                thread_id=event_id,
                deleted_at__isnull=True,
            ).select_related("file")
        )

        comment_attachments = [a for a in all_attachments if a.comment_id is not None]
        standalone_attachments = [a for a in all_attachments if a.comment_id is None]

        self.event: Event = event
        self.standalone_attachments: list[Attachment] = standalone_attachments
        self.comments: list[CommentStruct] = self._build_comment_structs(
            event.loaded_comments, comment_attachments
        )

    @classmethod
    def from_components(
        cls,
        event_row: "Event",
        comment_rows: "list[Comment]",
        attachment_rows: "list[Attachment]",
        file_rows: "list[File]",
        standalone_attachments: "list[Attachment] | None" = None,
    ) -> "EventDetailStruct":
        """Build from pre-fetched rows. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.event = event_row
        instance.standalone_attachments = standalone_attachments or []
        comment_atts = [a for a in attachment_rows if a.comment_id is not None]
        instance.comments = cls._build_comment_structs(comment_rows, comment_atts)
        return instance

    @staticmethod
    def _build_comment_structs(
        comment_rows: "list[Comment]",
        comment_attachment_rows: "list[Attachment]",
    ) -> "list[CommentStruct]":
        attachments_by_comment: dict[int, list] = defaultdict(list)
        for att in comment_attachment_rows:
            attachments_by_comment[att.comment_id].append(att)

        comment_structs = []
        for comment in comment_rows:
            atts = attachments_by_comment.get(comment.pk, [])
            files = [a.file for a in atts]
            comment_structs.append(CommentStruct.from_components(comment, atts, files))
        return comment_structs

    def to_dict(self) -> dict:
        from app.utils.hashids import encode_id

        return {
            "event_id": self.event.pk,
            "event_hash": encode_id(self.event.pk),
            "thread_type": self.event.thread_type,
            "allow_comments": self.event.allow_comments,
            "allow_direct_attachments": self.event.allow_direct_attachments,
            "title": self.event.title,
            "description": self.event.description,
            "event_type": self.event.event_type,
            "status": self.event.status,
            "priority": self.event.priority,
            "event_start": self.event.event_start.isoformat() if self.event.event_start else None,
            "event_end": self.event.event_end.isoformat() if self.event.event_end else None,
            "domain": self.event.domain.name if self.event.domain else None,
            "created_by": str(self.event.created_by) if self.event.created_by else None,
            "created_at": self.event.created_at.isoformat() if self.event.created_at else None,
            "comments": [c.to_dict() for c in self.comments],
            "standalone_attachments": [
                {
                    "attachment_id": str(a.id),
                    "file_id": str(a.file_id),
                    "attachment_type": a.attachment_type,
                    "caption": a.caption,
                    "display_order": a.display_order,
                    "original_filename": a.file.original_filename,
                    "file_size": a.file.file_size,
                    "mime_type": a.file.mime_type,
                }
                for a in self.standalone_attachments
            ],
        }
