"""Comment add / edit / soft-delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.events.control_layer.comment_context import CommentContext
from app.events.control_layer.handlers.comment_handler import CommentHandler
from app.events.models import Comment, Event
from app.utils.hashids import decode_hash, encode_id


def _resolve_event(event_hash: str) -> Event:
    event_id = decode_hash(event_hash)
    if event_id is None:
        raise Http404
    return get_object_or_404(Event.objects.active().select_related("domain", "created_by"), pk=event_id)


def _resolve_comment(comment_hash: str, event: Event) -> Comment:
    comment_id = decode_hash(comment_hash)
    if comment_id is None:
        raise Http404
    return get_object_or_404(
        Comment.objects.active().select_related("created_by"),
        pk=comment_id,
        activity_thread=event,
    )


@require_http_methods(["GET", "POST"])
def comment_add(request: HttpRequest, event_hash: str) -> HttpResponse:
    event = _resolve_event(event_hash)

    if request.method == "POST":
        result = CommentHandler(request.user).add(event, request.POST, request.FILES)
        if result.ok:
            messages.success(request, "Comment added.")
        else:
            messages.error(request, " ".join(result.errors))
        return redirect(reverse("event_detail", kwargs={"hash": event_hash}))

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

    if request.method == "POST":
        result = CommentHandler(request.user).edit(comment, request.POST, request.FILES)
        if result.ok:
            messages.success(request, "Comment updated.")
        else:
            messages.error(request, " ".join(result.errors))
        return redirect(reverse("event_detail", kwargs={"hash": event_hash}))

    from app.events.models import Attachment
    attachments = list(
        Attachment.objects.filter(comment=comment, deleted_at__isnull=True)
        .select_related("file")
        .order_by("display_order")
    )
    return render(request, "events/comment/edit_comment.html", {
        "event": event,
        "event_hash": event_hash,
        "comment": comment,
        "comment_hash": comment_hash,
        "attachments": attachments,
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
        return redirect(reverse("event_detail", kwargs={"hash": event_hash}))

    CommentContext(comment.pk, request.user).delete()
    messages.success(request, "Comment deleted.")
    return redirect(reverse("event_detail", kwargs={"hash": event_hash}))
