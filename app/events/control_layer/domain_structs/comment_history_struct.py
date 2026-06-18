"""CommentHistoryStruct — aggregated read model for a comment's full revision lineage."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment


class CommentRevisionRow:
    """
    One revision within a comment's history, paired with the attachments that
    belonged to it. Read-only; no mutations.
    """

    def __init__(
        self,
        comment: "Comment",
        attachments: "list[Attachment]",
        is_current: bool,
    ) -> None:
        self.comment = comment
        self.attachments = attachments
        self.is_current = is_current

    @property
    def comment_hash(self) -> str:
        from app.utils.hashids import encode_id

        return encode_id(self.comment.pk)

    def to_dict(self) -> dict:
        return {
            "comment_id": self.comment.pk,
            "comment_hash": self.comment_hash,
            "revision": self.comment.revision,
            "content": self.comment.content,
            "is_current": self.is_current,
            "created_by": str(self.comment.created_by) if self.comment.created_by else None,
            "created_at": self.comment.created_at.isoformat() if self.comment.created_at else None,
            "attachments": [
                {
                    "attachment_id": str(att.id),
                    "file_id": str(att.file_id),
                    "original_filename": att.file.original_filename,
                    "file_size": att.file.file_size,
                }
                for att in self.attachments
            ],
        }


class CommentHistoryStruct:
    """
    Full revision lineage for a single comment, newest (current) revision first.

    Comments are immutable: each edit soft-deletes the prior revision and creates
    a new row whose ``origin_id`` points back to it. This struct walks that chain
    backward from the given comment, then attaches each revision's attachment rows
    (including superseded/soft-deleted ones, so the historical record is intact).

    Read-only aggregate — owns no mutations.
    """

    def __init__(self, comment_id: int) -> None:
        from app.events.models import Attachment, Comment

        lineage = self._walk_lineage(comment_id)
        attachments_by_comment = self._group_attachments(
            Attachment.objects.filter(
                comment_id__in=[c.pk for c in lineage]
            ).select_related("file").order_by("display_order")
        )

        self.revisions: list[CommentRevisionRow] = [
            CommentRevisionRow(
                comment=comment,
                attachments=attachments_by_comment.get(comment.pk, []),
                is_current=(index == 0),
            )
            for index, comment in enumerate(lineage)
        ]

    @classmethod
    def from_components(
        cls,
        revisions: "list[CommentRevisionRow]",
    ) -> "CommentHistoryStruct":
        """Build from pre-assembled rows. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.revisions = revisions
        return instance

    @property
    def current(self) -> "Comment | None":
        return self.revisions[0].comment if self.revisions else None

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    def to_dict(self) -> dict:
        return {
            "current_comment_id": self.current.pk if self.current else None,
            "revision_count": self.revision_count,
            "revisions": [row.to_dict() for row in self.revisions],
        }

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _walk_lineage(comment_id: int) -> "list[Comment]":
        """
        Comments newest-first, following ``origin_id`` back through each
        superseded revision. Cycle-guarded against malformed chains.
        """
        from app.events.models import Comment

        head = Comment.objects.select_related("created_by").get(pk=comment_id)
        lineage: list[Comment] = [head]
        seen = {head.pk}
        current = head
        while current.origin_id_id and current.origin_id_id not in seen:
            parent = (
                Comment.objects.select_related("created_by")
                .filter(pk=current.origin_id_id)
                .first()
            )
            if parent is None:
                break
            lineage.append(parent)
            seen.add(parent.pk)
            current = parent
        return lineage

    @staticmethod
    def _group_attachments(attachments) -> "dict[int, list[Attachment]]":
        grouped: dict[int, list] = {}
        for attachment in attachments:
            grouped.setdefault(attachment.comment_id, []).append(attachment)
        return grouped
