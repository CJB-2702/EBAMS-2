from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment, File


class CommentStruct:
    """
    CommentStruct — data container for a single Comment and its related rows.

    Relationships:
    Comment (1)
        └── Attachment (0..N)  — join record
            └── File (1 per attachment)
    Optionally: soft-deleted previous revisions sharing the same origin_id chain.

    Example query for from_components():
    comment = Comment.objects.select_related("created_by").get(pk=comment_id)
    attachments = list(
        Attachment.objects.filter(
            comment_id=comment_id, deleted_at__isnull=True
        ).select_related("file")
    )
    files = [a.file for a in attachments]
    struct = CommentStruct.from_components(comment, attachments, files)
    """
    def __init__(self, comment_id: int, include_revisions: bool = False) -> None:
        from app.events.models import Attachment, Comment

        comment = (
            Comment.objects.select_related("created_by")
            .get(pk=comment_id)
        )
        attachments = list(
            Attachment.objects.filter(
                comment_id=comment_id, deleted_at__isnull=True
            ).select_related("file")
        )
        files = [a.file for a in attachments]

        revisions: list[Comment] = []
        if include_revisions:
            revisions = list(
                Comment.objects.select_related("created_by")
                .filter(origin_id=comment_id)
                .order_by("revision")
            )

        self.comment: Comment = comment
        self.attachments: list[Attachment] = attachments
        self.files: list[File] = files
        self.revisions: list[Comment] = revisions

    @classmethod
    def from_components(
        cls,
        comment_row: "Comment",
        attachments: "list[Attachment]",
        files: "list[File]",
        revisions: "list[Comment] | None" = None,
    ) -> "CommentStruct":
        """Build from pre-fetched rows. Issues no DB queries."""
        instance = cls.__new__(cls)
        instance.comment = comment_row
        instance.attachments = attachments
        instance.files = files
        instance.revisions = revisions or []
        return instance

    def to_dict(self) -> dict:
        from app.utils.hashids import encode_id

        return {
            "comment_id": self.comment.pk,
            "comment_hash": encode_id(self.comment.pk),
            "content": self.comment.content,
            "revision": self.comment.revision,
            "is_human_made": self.comment.is_human_made,
            "created_by": str(self.comment.created_by) if self.comment.created_by else None,
            "created_at": self.comment.created_at.isoformat() if self.comment.created_at else None,
            "attachments": [
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
                for a in self.attachments
            ],
        }
