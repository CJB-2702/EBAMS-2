"""EventContext — stateful control object for a single event."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.domain_structs.event_detail_struct import EventDetailStruct

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile


class EventContext:
    """
    Primary entry point for external callers working with an event.
    Owns cross-table write operations; delegates single-row writes to handlers.

    No create() method — event creation is handled by EventHandler.
    """

    def __init__(self, event_id: int, actor, include_shadow_comments: bool = False) -> None:
        self.struct = EventDetailStruct(event_id, include_shadow_comments=include_shadow_comments)
        self.actor = actor

    @classmethod
    def create_from_struct(cls, event_detail_struct: EventDetailStruct, actor) -> "EventContext":
        """Build from a pre-loaded struct. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.struct = event_detail_struct
        instance.actor = actor
        return instance

    def edit(self, post_data) -> object:
        from app.events.control_layer.handlers.event_handler import EventHandler
        return EventHandler(self.actor).edit(self.struct.event, post_data)

    def add_comment(self, post_data, *, is_human_made: bool = True) -> object:
        from app.events.control_layer.handlers.comment_handler import CommentHandler
        return CommentHandler(self.actor).add(
            self.struct.event, post_data, is_human_made=is_human_made
        )

    def add_attachment(self, uploaded_file: "UploadedFile") -> object:
        """Attach a file directly to the event as a standalone attachment."""
        from app.events.control_layer.handlers.direct_attachment_handler import (
            DirectAttachmentHandler,
        )
        return DirectAttachmentHandler(self.actor).attach(
            thread=self.struct.event, uploaded_file=uploaded_file
        )

    def delete(self) -> None:
        """
        Soft-delete the event, then cascade to all child comments.
        EventContext does not import Attachment or File directly —
        all child cleanup is delegated to CommentContext.
        """
        from app.events.control_layer.comment_context import CommentContext

        with transaction.atomic():
            self.struct.event._soft_delete(self.actor)

            for comment_struct in self.struct.comments:
                CommentContext.create_from_struct(comment_struct, self.actor).delete()
