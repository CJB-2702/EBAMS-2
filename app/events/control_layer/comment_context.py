"""CommentContext — stateful control object for a single comment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.events.control_layer.domain_structs.comment_struct import CommentStruct

if TYPE_CHECKING:
    from django.core.files.uploadedfile import UploadedFile
    from app.events.control_layer.handlers.file_handler import FileResult
    from app.events.models import Comment, Event


class CommentContext:
    """
    Owns the delete lifecycle for a comment. On delete, demotes attached files
    to standalone event attachments rather than cascading the deletion.

    No create() method — adding a comment is handled by CommentHandler.
    """

    def __init__(self, comment_id: int, actor) -> None:
        self.struct = CommentStruct(comment_id)
        self.actor = actor
        self._event = None
        self._domain = None

    @classmethod
    def create_from_struct(cls, comment_struct: CommentStruct, actor) -> "CommentContext":
        """Build from a pre-loaded struct. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.struct = comment_struct
        instance.actor = actor
        instance._event = None
        instance._domain = None
        return instance

    @property
    def event(self):
        if self._event is None:
            from app.events.models import Event
            self._event = Event.threads.select_related("domain").get(
                pk=self.struct.comment.activity_thread_id
            )
        return self._event

    @property
    def domain(self):
        if self._domain is None:
            self._domain = self.event.domain
        return self._domain

    def add_files(self, uploaded_files: "list[UploadedFile]") -> "list[FileResult]":
        """
        Attach one or more files to this comment in a single transaction.
        All uploads are rolled back if any file fails validation.
        Returns one FileResult per input file in the same order.
        """
        from app.events.control_layer.handlers.file_handler import FileHandler

        results: list[FileResult] = []
        with transaction.atomic():
            for uploaded_file in uploaded_files:
                result = FileHandler(self.actor).upload(
                    self.event, uploaded_file, comment=self.struct.comment
                )
                results.append(result)
                if not result.ok:
                    transaction.set_rollback(True)
        return results

    def edit(self, post_data) -> object:
        from app.events.control_layer.handlers.comment_handler import CommentHandler
        return CommentHandler(self.actor).edit(self.struct.comment, post_data)

    def delete(self) -> None:
        with transaction.atomic():
            # Demote comment-linked attachments to standalone event attachments.
            # Files are never deleted as a side effect of comment deletion.
            self.struct.comment.attachments.filter(deleted_at__isnull=True).update(comment=None)
            self.struct.comment._soft_delete(self.actor)
