"""File upload / download / soft-delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.events.control_layer.event_context import EventContext
from app.events.control_layer.file_context import FileContext
from app.events.control_layer.handlers.comment_attachment_handler import (
    CommentAttachmentHandler,
)
from app.events.models import Comment, Event, File
from app.events.presentation_layer.entrypoints.events import _check_domain_access
from app.utils.hashids import decode_hash


@require_http_methods(["POST"])
def direct_attachment_add(request: HttpRequest, event_hash: str) -> HttpResponse:
    """Attach one or more files directly to a thread (not to a comment) —
    the "+" upload button on the Files card in events/fragments/event_card.html."""
    event_id = decode_hash(event_hash)
    if event_id is None:
        raise Http404
    event = get_object_or_404(Event.objects.active().select_related("domain", "created_by"), pk=event_id)

    if not event.allow_direct_attachments or not _check_domain_access(request, event):
        return HttpResponseForbidden("You may not attach files to this thread.")

    uploaded_files = [f for f in request.FILES.getlist("files") if getattr(f, "name", None)]
    ctx = EventContext(event.pk, request.user)
    errors: list[str] = []
    for uploaded_file in uploaded_files:
        result = ctx.add_attachment(uploaded_file)
        if not result.ok:
            errors.extend(result.errors)

    if request.headers.get("HX-Request") and request.GET.get("format") == "htmx-event-card":
        from app.events.presentation_layer.entrypoints.events import build_event_card

        return render(request, "events/fragments/event_card.html", {
            "card": build_event_card(event, request.user),
            "attachment_error": " ".join(errors) if errors else "",
        })

    if errors:
        messages.error(request, " ".join(errors))
    elif uploaded_files:
        messages.success(request, "File(s) uploaded.")
    return redirect(reverse("event_detail", kwargs={"hash": event_hash}))


@require_http_methods(["POST"])
def file_upload(request: HttpRequest, event_hash: str) -> HttpResponse:
    event_id = decode_hash(event_hash)
    if event_id is None:
        raise Http404
    event = get_object_or_404(Event.objects.active(), pk=event_id)

    comment_hash = request.POST.get("comment_hash", "").strip()
    comment_id = decode_hash(comment_hash) if comment_hash else None
    if comment_id is None:
        messages.error(request, "Invalid comment reference.")
        return redirect(reverse("event_detail", kwargs={"hash": event_hash}))

    comment = get_object_or_404(Comment.objects.active(), pk=comment_id, activity_thread=event)

    can_attach = (
        comment.created_by == request.user
        or request.user.has_perm("events.can_edit_others_comments")
    )
    if not can_attach:
        return HttpResponseForbidden("You may not attach files to this comment.")

    result = CommentAttachmentHandler(request.user).attach(
        comment=comment, uploaded_file=request.FILES.get("file")
    )
    if result.ok:
        messages.success(request, f"File '{result.file.original_filename}' uploaded.")
    else:
        messages.error(request, " ".join(result.errors))

    return redirect(reverse("event_detail", kwargs={"hash": event_hash}))


@require_http_methods(["GET"])
def file_download(request: HttpRequest, file_id: str) -> HttpResponse:
    event_file = get_object_or_404(File.objects.filter(deleted_at__isnull=True), pk=file_id)
    if not event_file.file:
        return HttpResponseNotFound("File not available.")
    response = FileResponse(event_file.file.open("rb"), as_attachment=True)
    response["Content-Disposition"] = f'attachment; filename="{event_file.original_filename}"'
    return response


@require_http_methods(["GET"])
def file_inline(request: HttpRequest, file_id: str) -> HttpResponse:
    event_file = get_object_or_404(File.objects.filter(deleted_at__isnull=True), pk=file_id)
    if not event_file.file:
        return HttpResponseNotFound("File not available.")
    mime = event_file.mime_type or "application/octet-stream"
    response = FileResponse(event_file.file.open("rb"), content_type=mime)
    response["Content-Disposition"] = f'inline; filename="{event_file.original_filename}"'
    return response


@require_http_methods(["POST"])
def file_soft_delete(request: HttpRequest, file_id: str) -> HttpResponse:
    event_file = get_object_or_404(File.objects.filter(deleted_at__isnull=True), pk=file_id)
    referer = request.META.get("HTTP_REFERER", reverse("event_index"))

    result = FileContext.from_file(event_file, request.user).delete()
    if result.ok:
        messages.success(request, "File deleted.")
    else:
        messages.error(request, " ".join(result.errors))

    return redirect(referer)
