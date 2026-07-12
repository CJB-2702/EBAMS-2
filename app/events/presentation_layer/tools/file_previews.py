"""File preview utilities — read-only, presentation layer only."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.control_layer.domain_structs.event_detail_struct import EventDetailStruct
    from app.events.models import File


def get_text_snippet(event_file: "File", max_chars: int = 50) -> str:
    try:
        with event_file.file.open("r") as fh:
            return fh.read(max_chars)
    except Exception:
        return ""


def build_comment_row(comment) -> dict:
    """
    Single-comment counterpart to build_comments_context() — used to re-render
    just one row (events/fragments/comment_row.html) after an inline HTMX edit,
    where we only have the freshly-saved Comment, not a whole EventDetailStruct.
    Each entry: {comment, comment_hash, attachments: [{attachment, snippet}]}
    """
    from app.events.models import Attachment
    from app.utils.hashids import encode_id

    att_data = []
    for att in (
        Attachment.objects.filter(comment=comment, deleted_at__isnull=True)
        .select_related("file")
        .order_by("display_order")
    ):
        if att.file.deleted_at is not None:
            continue
        snippet = get_text_snippet(att.file) if att.file.is_text_preview() else None
        att_data.append({"attachment": att, "snippet": snippet})
    return {
        "comment": comment,
        "comment_hash": encode_id(comment.pk),
        "attachments": att_data,
    }


def build_comments_context(struct: "EventDetailStruct") -> list[dict]:
    """
    Process an EventDetailStruct into a flat list for template rendering.
    Each entry: {comment, comment_hash, attachments: [{attachment, snippet}]}
    """
    from app.utils.hashids import encode_id

    result = []
    for comment_struct in struct.comments:
        att_data = []
        for att in comment_struct.attachments:
            if att.file.deleted_at is not None:
                continue
            snippet = get_text_snippet(att.file) if att.file.is_text_preview() else None
            att_data.append({"attachment": att, "snippet": snippet})
        result.append({
            "comment": comment_struct.comment,
            "comment_hash": encode_id(comment_struct.comment.pk),
            "attachments": att_data,
        })
    return result
