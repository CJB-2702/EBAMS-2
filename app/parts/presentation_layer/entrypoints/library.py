"""Part library — the technical document store for a part.

One card for the base part plus one card per revision. Each card lists its
attachments (model photos, drawings, manuals, …) and — for users holding the
``parts.change_part`` capability — lets them add or remove files. This is the
engineering document store, not a place for invoices or receipts; that intent
is stated on the page itself.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
)
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.parts.control_layer.domain_structs.part_structs.part_struct import (
    PartNotFoundError,
)
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.parts.control_layer.part_context import PartContext

# Managing the library (adding/removing technical documents) is gated behind the
# same capability that lets a user edit the part itself.
LIBRARY_MANAGE_PERM = "parts.change_part"


def _ctx_or_404(request: HttpRequest, part_id: int) -> PartContext:
    try:
        return PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404


def _resolve_owner(ctx: PartContext, revision_id: str | None):
    """Return ``(owner, thread_attr)`` for the section named by ``revision_id`` —
    the base Part's ``documents_thread`` when empty, otherwise the matching
    PartRevision's own ``thread`` (404 if it isn't this part's)."""
    if not revision_id:
        return ctx.part, "documents_thread"
    for revision in ctx.revisions():
        if str(revision.id) == str(revision_id):
            return revision, "thread"
    raise Http404


@require_http_methods(["GET"])
def part_library(request: HttpRequest, part_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, part_id)
    can_manage = request.user.has_perm(LIBRARY_MANAGE_PERM)

    base_documents = ActivityThreadManager(
        ctx.part, request.user, thread_attr="documents_thread"
    ).documents()
    revision_sections = [
        {
            "id": revision.id,
            "label": f"{revision.major_revision_number}.{revision.minor_revision_number}",
            "name": revision.major_revision_name,
            "status": revision.status,
            "documents": ActivityThreadManager(revision, request.user).documents(),
        }
        for revision in ctx.revisions()
    ]

    return render(
        request,
        "parts/library.html",
        {
            "part": ctx.part,
            "part_id": part_id,
            "can_manage": can_manage,
            "base_documents": base_documents,
            "revision_sections": revision_sections,
        },
    )


@require_http_methods(["POST"])
def library_add_document(request: HttpRequest, part_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, part_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not add documents to this library.")

    revision_id = request.POST.get("revision_id", "").strip()
    owner, thread_attr = _resolve_owner(ctx, revision_id)
    uploaded_files = request.FILES.getlist("file")
    if not uploaded_files:
        messages.error(request, "Choose at least one file to add.")
        return redirect(reverse("part_library", kwargs={"part_id": part_id}))

    caption = request.POST.get("caption", "").strip()
    manager = ActivityThreadManager(owner, request.user, thread_attr=thread_attr)
    added = 0
    for uploaded in uploaded_files:
        result = manager.attach_document(uploaded, caption=caption)
        if result.ok:
            added += 1
        else:
            for error in result.errors:
                messages.error(request, f"{uploaded.name}: {error}")
    if added:
        messages.success(
            request,
            f"{added} document{'' if added == 1 else 's'} added to the library.",
        )
    return redirect(reverse("part_library", kwargs={"part_id": part_id}))


@require_http_methods(["POST"])
def library_remove_document(request: HttpRequest, part_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, part_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not remove documents from this library.")

    revision_id = request.POST.get("revision_id", "").strip()
    attachment_id = request.POST.get("attachment_id", "").strip()
    owner, thread_attr = _resolve_owner(ctx, revision_id)
    if not attachment_id:
        messages.error(request, "No document specified.")
        return redirect(reverse("part_library", kwargs={"part_id": part_id}))

    if ActivityThreadManager(owner, request.user, thread_attr=thread_attr).detach_document(
        attachment_id
    ):
        # Removing the current hero image must not leave the part pointing at a
        # deleted attachment — promote the next image (or clear the FK).
        ctx.images.resync_primary(attachment_id)
        messages.success(request, "Document removed from the library.")
    else:
        messages.error(request, "Document not found in this library section.")
    return redirect(reverse("part_library", kwargs={"part_id": part_id}))
