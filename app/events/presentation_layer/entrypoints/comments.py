"""Comment add / edit / soft-delete entrypoints."""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.events.control_layer.comment_context import CommentContext
from app.events.control_layer.domain_structs.comment_history_struct import CommentHistoryStruct
from app.events.control_layer.handlers.comment_handler import CommentHandler
from app.events.models import Comment, Event
from app.events.presentation_layer.entrypoints.events import _check_domain_access
from app.utils.hashids import decode_hash, encode_id
from app.utils.safe_redirect import safe_next_url


def _resolve_event(event_hash: str) -> Event:
    """Resolve any row in the shared event table by hash — an Event, or a
    non-Event activity thread (Part/AssetModel/…). ``Event.threads`` resolves
    any thread type; comment management is done through these base events
    views regardless of which app's thread it lives on."""
    event_id = decode_hash(event_hash)
    if event_id is None:
        raise Http404
    return get_object_or_404(Event.threads.select_related("domain", "created_by"), pk=event_id)


def _redirect_after(request: HttpRequest, event_hash: str) -> HttpResponse:
    """Return to the caller-supplied ``next`` (e.g. a Part or AssetModel page)
    when it is a safe same-host URL; otherwise fall back to the event detail
    page — today's behavior for the events app itself."""
    return redirect(safe_next_url(request, reverse("event_detail", kwargs={"hash": event_hash})))


def _resolve_comment(comment_hash: str, event: Event) -> Comment:
    comment_id = decode_hash(comment_hash)
    if comment_id is None:
        raise Http404
    return get_object_or_404(
        Comment.objects.active().select_related("created_by"),
        pk=comment_id,
        activity_thread=event,
    )


def _attachments_json(attachments) -> str:
    """Serialize Attachment rows for <add-comment>'s existing-attachments
    attribute (mode="edit") — see add_comment.js."""
    return json.dumps([
        {
            "id": str(att.id),
            "name": att.file.original_filename,
            "size": att.file.file_size,
            "is_image": att.file.is_image(),
        }
        for att in attachments
    ])


@require_http_methods(["GET", "POST"])
def comment_add(request: HttpRequest, event_hash: str) -> HttpResponse:
    event = _resolve_event(event_hash)

    if request.method == "POST":
        result = CommentHandler(request.user).add(event, request.POST, request.FILES)

        # Inline add from the expanded card view: re-render just that card so
        # the new comment appears without leaving the list.
        if request.headers.get("HX-Request") and request.GET.get("format") == "htmx-event-card":
            from app.events.presentation_layer.entrypoints.events import build_event_card

            return render(request, "events/fragments/event_card.html", {
                "card": build_event_card(event, request.user),
                "comment_error": "" if result.ok else " ".join(result.errors),
            })

        if result.ok:
            messages.success(request, "Comment added.")
        else:
            messages.error(request, " ".join(result.errors))
        return _redirect_after(request, event_hash)

    return render(request, "events/comment/add_comment.html", {
        "event": event,
        "event_hash": event_hash,
    })


@require_http_methods(["GET", "POST"])
def comment_edit(request: HttpRequest, event_hash: str, comment_hash: str) -> HttpResponse:
    event = _resolve_event(event_hash)
    comment = _resolve_comment(comment_hash, event)

    can_edit = (
        comment.created_by == request.user
        or request.user.has_perm("events.can_edit_others_comments")
    )
    if not can_edit:
        return HttpResponseForbidden("You may not edit this comment.")

    # Inline HTMX editing: the Edit button on comment_row.html swaps the row
    # for this same view's fragment, and row_depth/action_depth round-trip
    # (query on GET, hidden field on POST) so the swapped-back row keeps its
    # ambient nesting depth (see events/fragments/comments_card.html's
    # row_depth/action_depth params).
    row_depth = request.GET.get("row_depth", "") or request.POST.get("row_depth", "")
    action_depth = request.GET.get("action_depth", "") or request.POST.get("action_depth", "")
    inline = request.headers.get("HX-Request") and request.GET.get("format") == "htmx-comment-row"

    if request.method == "POST":
        remove_ids = request.POST.getlist("remove_attachments")
        result = CommentHandler(request.user).edit(
            comment, request.POST, request.FILES, remove_attachment_ids=remove_ids
        )

        if inline:
            if result.ok:
                from app.events.presentation_layer.tools.file_previews import build_comment_row

                return render(request, "events/fragments/comment_row.html", {
                    "row": build_comment_row(result.comment),
                    "event_hash": event_hash,
                    "row_depth": row_depth,
                    "action_depth": action_depth,
                })
            from app.events.models import Attachment
            attachments = list(
                Attachment.objects.filter(comment=comment, deleted_at__isnull=True)
                .select_related("file")
                .order_by("display_order")
            )
            return render(request, "events/comment/fragments/comment_edit_form.html", {
                "event": event,
                "event_hash": event_hash,
                "comment": comment,
                "comment_hash": comment_hash,
                "attachments": attachments,
                "existing_attachments_json": _attachments_json(attachments),
                "row_depth": row_depth,
                "action_depth": action_depth,
                "errors": result.errors,
            })

        if result.ok:
            messages.success(request, "Comment updated.")
        else:
            messages.error(request, " ".join(result.errors))
        return _redirect_after(request, event_hash)

    from app.events.models import Attachment
    attachments = list(
        Attachment.objects.filter(comment=comment, deleted_at__isnull=True)
        .select_related("file")
        .order_by("display_order")
    )
    ctx = {
        "event": event,
        "event_hash": event_hash,
        "comment": comment,
        "comment_hash": comment_hash,
        "attachments": attachments,
        "row_depth": row_depth,
        "action_depth": action_depth,
    }
    if inline:
        return render(request, "events/comment/fragments/comment_edit_form.html", {
            **ctx, "existing_attachments_json": _attachments_json(attachments),
        })
    return render(request, "events/comment/edit_comment.html", ctx)


@require_http_methods(["GET"])
def comment_view_row(request: HttpRequest, event_hash: str, comment_hash: str) -> HttpResponse:
    """Read-only comment row fragment — HTMX-loaded to cancel out of the inline
    edit form (events/comment/fragments/comment_edit_form.html) back to the
    normal comment_row.html view."""
    event = _resolve_event(event_hash)
    if not _check_domain_access(request, event):
        return HttpResponseForbidden("You do not have access to this event.")
    comment = _resolve_comment(comment_hash, event)

    from app.events.presentation_layer.tools.file_previews import build_comment_row

    return render(request, "events/fragments/comment_row.html", {
        "row": build_comment_row(comment),
        "event_hash": event_hash,
        "row_depth": request.GET.get("row_depth", ""),
        "action_depth": request.GET.get("action_depth", ""),
    })


@require_http_methods(["GET"])
def comment_gallery(request: HttpRequest, event_hash: str, comment_hash: str) -> HttpResponse:
    """Lazy-loaded gallery fragment for one comment's image attachments —
    HTMX-loaded (hx-trigger="revealed") into the "View as gallery" modal in
    events/comment/fragments/attachment_mini_cards.html."""
    event = _resolve_event(event_hash)
    if not _check_domain_access(request, event):
        return HttpResponseForbidden("You do not have access to this event.")
    comment = _resolve_comment(comment_hash, event)

    from app.events.models import Attachment
    from app.events.presentation_layer.tools.generic_cards import document_dict

    images = [
        document_dict(a)
        for a in Attachment.objects.filter(comment=comment, deleted_at__isnull=True)
        .select_related("file")
        .filter(file__deleted_at__isnull=True)
        if a.file.is_image()
    ]
    return render(request, "events/fragments/gallery_card.html", {
        "images": images,
        "dom_id": comment_hash,
    })


@require_http_methods(["GET"])
def comment_history(request: HttpRequest, event_hash: str, comment_hash: str) -> HttpResponse:
    """Read-only revision history for a single comment lineage."""
    event = _resolve_event(event_hash)
    if not _check_domain_access(request, event):
        return HttpResponseForbidden("You do not have access to this event.")
    
    can_edit = (
        event.created_by == request.user
        or request.user.has_perm("events.can_edit_others_events")
    )
    if not can_edit:
        return HttpResponseForbidden("You may not view this comment history.")

    comment = _resolve_comment(comment_hash, event)
    history = CommentHistoryStruct(comment.pk)

    return render(request, "events/comment/history.html", {
        "event": event,
        "event_hash": event_hash,
        "comment_hash": comment_hash,
        "rows": history.revisions,
        "revision_count": history.revision_count,
    })


@require_http_methods(["POST"])
def comment_soft_delete(request: HttpRequest, event_hash: str, comment_hash: str) -> HttpResponse:
    event = _resolve_event(event_hash)
    comment = _resolve_comment(comment_hash, event)

    can_delete = (
        comment.created_by == request.user
        or request.user.has_perm("events.can_edit_others_comments")
    )
    if not can_delete:
        messages.error(request, "You may not delete this comment.")
        return _redirect_after(request, event_hash)

    CommentContext(comment.pk, request.user).delete()
    messages.success(request, "Comment deleted.")
    return _redirect_after(request, event_hash)
