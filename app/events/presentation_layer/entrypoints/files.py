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
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.events.control_layer.file_context import FileContext
from app.events.control_layer.handlers.file_handler import FileHandler
from app.events.models import Comment, Event, File
from app.utils.hashids import decode_hash


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

    result = FileHandler(request.user).upload(event, request.FILES.get("file"), comment=comment)
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
