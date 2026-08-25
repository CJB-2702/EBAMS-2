"""Model library — the composed document/gallery store for a model line.

One card per version of a model (every AssetModel sharing a ``model_name``),
ordered by ``version_rank``. Each card shows that version's image gallery,
technical document library and comments. Users holding ``assets.change_assetmodel``
may add/remove files and images, set the hero image, and post comments.

Reads are keyed by ``model_name`` (the composed view spans all versions); writes
are keyed by the specific version's ``model_id`` and redirect back to the library.
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

from app.assets.control_layer.asset_model_context import AssetModelContext
from app.assets.control_layer.domain_structs.asset_model_struct import (
    AssetModelNotFoundError,
    AssetModelStruct,
)
from app.assets.presentation_layer.search.asset_model_search import load_model_versions
from app.events.control_layer.managers.gallery_manager import GalleryError
from app.utils.safe_redirect import safe_next_url

LIBRARY_MANAGE_PERM = "assets.change_assetmodel"


def _ctx_or_404(request: HttpRequest, model_id: int) -> AssetModelContext:
    try:
        return AssetModelContext(model_id, actor=request.user)
    except AssetModelNotFoundError:
        raise Http404


def _library_redirect(model_name: str) -> HttpResponse:
    return redirect(reverse("model_library", kwargs={"model_name": model_name}))


def _redirect_after(request: HttpRequest, model_name: str) -> HttpResponse:
    """Return to the caller-supplied ``next`` (e.g. the model edit page) when it is a
    safe same-host URL; otherwise fall back to the model library page."""
    return redirect(safe_next_url(request, reverse("model_library", kwargs={"model_name": model_name})))


@require_http_methods(["GET"])
def model_library(request: HttpRequest, model_name: str) -> HttpResponse:
    versions = list(load_model_versions(model_name))
    if not versions:
        raise Http404

    can_manage = request.user.has_perm(LIBRARY_MANAGE_PERM)
    sections = []
    for model in versions:
        ctx = AssetModelContext.from_struct(
            AssetModelStruct.from_instance(model), request.user
        )
        sections.append(
            {
                "id": model.id,
                "version": model.version,
                "version_rank": model.version_rank,
                "is_base_model": model.is_base_model,
                "asset_class": model.asset_class.name,
                "documents": ctx.documents.documents(),
                "images": ctx.images.image_dicts(),
                "comments_card": ctx.documents.card(request.user),
            }
        )

    return render(
        request,
        "assets/models/library.html",
        {
            "model_name": model_name,
            "sections": sections,
            "can_manage": can_manage,
        },
    )


@require_http_methods(["POST"])
def library_add_document(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not add documents to this library.")

    uploaded_files = request.FILES.getlist("file")
    if not uploaded_files:
        messages.error(request, "Choose at least one file to add.")
        return _redirect_after(request, ctx.model.model_name)

    caption = request.POST.get("caption", "").strip()
    added = 0
    for uploaded in uploaded_files:
        result = ctx.documents.attach_document(uploaded, caption=caption)
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
    return _redirect_after(request, ctx.model.model_name)


@require_http_methods(["POST"])
def library_remove_document(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not remove documents from this library.")

    attachment_id = request.POST.get("attachment_id", "").strip()
    if not attachment_id:
        messages.error(request, "No document specified.")
    elif ctx.documents.detach_document(attachment_id):
        messages.success(request, "Document removed from the library.")
    else:
        messages.error(request, "Document not found in this library section.")
    return _redirect_after(request, ctx.model.model_name)


@require_http_methods(["POST"])
def library_add_image(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not add images to this gallery.")

    caption = request.POST.get("caption", "").strip()
    uploaded_files = request.FILES.getlist("file")
    if not uploaded_files:
        messages.error(request, "Choose at least one image to add.")
        return _redirect_after(request, ctx.model.model_name)

    added = 0
    for uploaded in uploaded_files:
        try:
            ctx.images.add_image(uploaded, caption=caption)
            added += 1
        except GalleryError as exc:
            messages.error(request, str(exc))
    if added:
        messages.success(
            request,
            f"{added} image{'' if added == 1 else 's'} added to the gallery.",
        )
    return _redirect_after(request, ctx.model.model_name)


@require_http_methods(["POST"])
def library_remove_image(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not remove images from this gallery.")

    attachment_id = request.POST.get("attachment", "").strip()
    if attachment_id and ctx.images.remove_image(attachment_id):
        messages.success(request, "Image removed from the gallery.")
    else:
        messages.error(request, "Image not found in this gallery.")
    return _redirect_after(request, ctx.model.model_name)


@require_http_methods(["POST"])
def library_set_primary_image(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not change the hero image.")

    attachment_id = request.POST.get("attachment", "").strip()
    try:
        ctx.images.set_primary(attachment_id)
        messages.success(request, "Primary image updated.")
    except GalleryError as exc:
        messages.error(request, str(exc))
    return _redirect_after(request, ctx.model.model_name)


@require_http_methods(["POST"])
def library_add_comment(request: HttpRequest, model_id: int) -> HttpResponse:
    ctx = _ctx_or_404(request, model_id)
    if not request.user.has_perm(LIBRARY_MANAGE_PERM):
        return HttpResponseForbidden("You may not comment on this model.")

    body = request.POST.get("content", "").strip()
    if not body:
        messages.error(request, "Comment cannot be empty.")
    else:
        ctx.documents.add_comment(body)
        messages.success(request, "Comment posted.")
    return _redirect_after(request, ctx.model.model_name)
