"""
Adapters from events domain objects to the generic card dict contract.

This is the same plain-dict shape app/events/control_layer/managers/activity_thread_manager.py
already produces for its documents()/comments() methods. Any card fragment under
events/fragments/{comments,gallery,files}_card.html is written against this contract,
not against events model objects — so the same fragments can render data sourced from
any sub-application's thread manager, as long as it's shaped into these dicts first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.events.models import Attachment, Comment, Event


def document_dict(attachment: "Attachment") -> dict:
    """Attachment -> generic document dict (gallery_card / files_card contract)."""
    file = attachment.file
    return {
        "id": str(attachment.id),
        "file_id": str(attachment.file_id),
        "filename": file.original_filename,
        "caption": attachment.caption,
        "icon": file.get_icon_class(),
        "is_image": file.is_image(),
        "file_size": file.file_size,
        "created_at": attachment.created_at.isoformat(),
        "created_at_display": attachment.created_at.strftime("%b %d, %Y"),
        "created_by": str(attachment.created_by) if attachment.created_by_id else "—",
    }


def comment_dict(comment: "Comment", attachments: "list[Attachment] | None" = None) -> dict:
    """Comment (+ its attachments) -> generic comment dict (comments_card contract)."""
    return {
        "id": comment.pk,
        "author": str(comment.created_by) if comment.created_by_id else "system",
        "body": comment.content,
        "created_at": comment.created_at,
        "is_human_made": comment.is_human_made,
        "attachments": [document_dict(a) for a in (attachments or [])],
    }


def build_activity_card(thread: "Event", user) -> dict:
    """Any activity-thread row (Event, ActivityThread, ...) -> the rich card
    contract ``events/fragments/comments_card.html`` + ``comment_row.html``
    render: {event, hash, comments, direct_attachments}. ``events.threads``
    resolves any thread type (see Event.threads), so this works unmodified for
    a Part's ``documents_thread``/``gallery_thread`` or an AssetModel's
    ``documentation`` thread — every app renders comments through this one
    function, never a per-app equivalent."""
    from app.events.control_layer.event_context import EventContext
    from app.events.presentation_layer.tools.file_previews import build_comments_context
    from app.utils.hashids import encode_id

    ctx = EventContext(thread.pk, user, include_shadow_comments=True)
    return {
        "event": thread,
        "hash": encode_id(thread.pk),
        "comments": build_comments_context(ctx.struct),
        "direct_attachments": [document_dict(a) for a in ctx.struct.standalone_attachments],
    }
