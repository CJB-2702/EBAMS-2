"""Parts hub, detail, create/edit — wired to the control layer."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.part_create_adaptor import PartCreateAdaptor
from app.parts.control_layer.domain_structs.part_struct import (
    PartNotFoundError,
    PartStruct,
)
from app.parts.control_layer.factories.part_factory import (
    PartFactory,
    PartValidationError,
)
from app.parts.control_layer.managers.part_manager import (
    PartValidationError as PartEditValidationError,
)
from app.parts.control_layer.part_context import PartContext
from app.parts.models import Part


@require_http_methods(["GET"])
def parts_hub(request: HttpRequest) -> HttpResponse:
    recent = Part.objects.order_by("-created_at")[:10]
    return render(request, "parts/hub.html", {"recent_parts": recent})


@require_http_methods(["GET"])
def part_detail(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user, eager=True)
    except PartNotFoundError:
        raise Http404
    documents = ctx.documents()
    return render(
        request,
        "parts/detail.html",
        {
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "revisions": ctx.revisions(),
            "documents": documents,
            "image_documents": [d for d in documents if d["is_image"]],
            "other_documents": [d for d in documents if not d["is_image"]],
            "comments": ctx.comments(),
            "supplier_items": [s.to_dict() for s in ctx.supplier_items()],
            "domains": Domain.objects.order_by("name"),
        },
    )


@require_http_methods(["GET", "POST"])
def part_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = PartCreateAdaptor.from_post(request.POST)
        try:
            part = PartFactory.create(data=data, actor=request.user)
        except PartValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(request, "parts/form.html", {"mode": "create", "part": data})
        messages.success(request, f"Part '{part.part_number}' created.")
        return redirect(reverse("part_detail", kwargs={"part_id": part.id}))
    return render(request, "parts/form.html", {"mode": "create", "part": None})


@require_http_methods(["GET", "POST"])
def part_edit(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    if request.method == "POST":
        data = PartCreateAdaptor.from_post(request.POST)
        try:
            ctx.update(data=data)
        except PartEditValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "parts/form.html",
                {"mode": "edit", "part": data, "part_id": part_id},
            )
        messages.success(request, f"Part '{ctx.part.part_number}' updated.")
        return redirect(reverse("part_detail", kwargs={"part_id": part_id}))
    return render(
        request,
        "parts/form.html",
        {"mode": "edit", "part": ctx.struct().to_dict(), "part_id": part_id},
    )


@require_http_methods(["POST"])
def part_add_comment(request: HttpRequest, part_id: int) -> HttpResponse:
    body = request.POST.get("body", "").strip()
    domain_id = request.POST.get("domain")
    if body and domain_id:
        PartContext(part_id, actor=request.user).thread.add_comment(
            body, domain_id=int(domain_id)
        )
        messages.success(request, "Comment added.")
    return redirect(reverse("part_detail", kwargs={"part_id": part_id}))


def _struct_or_404(part_id: int) -> PartStruct:
    try:
        return PartStruct(part_id)
    except PartNotFoundError:
        raise Http404
