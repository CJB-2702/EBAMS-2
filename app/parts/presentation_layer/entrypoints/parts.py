"""Parts hub, detail, create/edit — wired to the control layer."""

from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain, DomainTemplate
from app.parts.control_layer.adapters.part_create_adaptor import PartCreateAdaptor
from app.parts.control_layer.adapters.part_creation_wizard_adaptor import (
    PartCreationWizardAdaptor,
)
from app.parts.control_layer.domain_structs.part_structs.part_definition_struct import (
    PartDefinitionStruct,
)
from app.parts.control_layer.domain_structs.part_structs.part_struct import (
    PartNotFoundError,
    PartStruct,
)
from app.parts.control_layer.errors import PartValidationError
from app.parts.control_layer.factories.part_creation_wizard_factory import (
    PartCreationWizardFactory,
)
from app.parts.control_layer.handlers.part_domain_template_handler import (
    PartDomainTemplateHandler,
)
from app.parts.control_layer.managers.part_image_manager import PartImageError
from app.parts.control_layer.managers.part_manufacturer_manager import (
    PartManufacturerValidationError,
)
from app.parts.control_layer.managers.supplier_item_manager import (
    SupplierItemValidationError,
)
from app.parts.control_layer.part_context import PartContext
from app.parts.presentation_layer.search.part_search import search_parts
from app.procurement.presentation_layer.tools.recent_part_creations import (
    record_created_parts,
)
from app.utils.safe_redirect import safe_next_url


@require_http_methods(["GET"])
def parts_hub(request: HttpRequest) -> HttpResponse:
    filters = {
        key: request.GET.get(key, "").strip()
        for key in ("part_number", "name", "description", "manufacturer", "revision_name")
    }
    parts = search_parts(**filters)
    return render(request, "parts/hub.html", {"parts": parts, **filters})


@require_http_methods(["GET"])
def part_detail(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        definition = PartDefinitionStruct.from_id(part_id)
    except PartNotFoundError:
        raise Http404
    part = definition.to_dict()
    # The Part-level thread feeds are not part of the definition aggregate — load
    # them via the thread managers.
    ctx = PartContext.from_struct(definition.part_struct, actor=request.user)
    # Base part documents = the whole technical library, on documents_thread
    # (decoupled from revisions).
    base_documents = ctx.documents_thread.documents()
    # Gallery = image attachments on the Part's own gallery_thread (decoupled
    # from revisions).
    primary_id = str(definition.part_struct.part.primary_image_id or "")
    image_documents = [d for d in ctx.gallery.documents() if d["is_image"]]
    for d in image_documents:
        d["is_primary"] = d["id"] == primary_id
    # Current-revision documents still live on the current revision's own thread.
    other_documents = [d for d in ctx.documents() if not d["is_image"]]
    return render(
        request,
        "parts/detail.html",
        {
            "part": part,
            "part_id": part_id,
            "revisions": part["revisions"],
            "base_documents": base_documents,
            "image_documents": image_documents,
            "other_documents": other_documents,
            "comments_card": ctx.documents_thread.card(request.user),
            "supplier_items": part["supplier_items"],
            "domains": Domain.objects.order_by("name"),
        },
    )


@require_http_methods(["GET", "POST"])
def part_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = PartCreationWizardAdaptor.from_post(request.POST)
        try:
            part = PartCreationWizardFactory.create(data=data, actor=request.user)
        except (PartValidationError, SupplierItemValidationError, PartManufacturerValidationError) as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("part_create"))
        # DELIBERATE ANTI-PATTERN (D81) — see recent_part_creations.py.
        domain_ids = list(part.domain_access_mappings.filter(is_active=True).values_list("domain_id", flat=True))
        transaction.on_commit(
            lambda: record_created_parts(
                request, part_ids=[part.id], domain_ids_by_part={part.id: domain_ids}
            )
        )
        messages.success(request, f"Part '{part.part_number}' created.")
        return redirect(reverse("part_detail", kwargs={"part_id": part.id}))
    return render(
        request,
        "parts/create_wizard.html",
        {
            "domains": Domain.objects.order_by("name"),
            "domain_templates": DomainTemplate.objects.filter(is_active=True).order_by("name"),
        },
    )


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
        except PartValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("part_edit", kwargs={"part_id": part_id}))
        messages.success(request, f"Part '{ctx.part.part_number}' updated.")
        return redirect(reverse("part_detail", kwargs={"part_id": part_id}))
    return render(
        request,
        "parts/form.html",
        {
            "mode": "edit",
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "domain_templates": DomainTemplate.objects.filter(is_active=True).order_by("name"),
            **_domain_scope_context(ctx),
        },
    )


@require_http_methods(["POST"])
def part_move_domains(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    ids = [int(v) for v in request.POST.getlist("domain_ids") if v.strip().isdigit()]
    direction = request.POST.get("direction", "add")
    if ids:
        for domain_id in ids:
            if direction == "add":
                ctx.domain_scope.add_domain(domain_id)
            else:
                ctx.domain_scope.remove_domain(domain_id)

    msg = "Domains updated." if direction == "add" else "Domains removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "parts/_domains_dlb_only.html", _domain_scope_context(ctx)).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def part_domains_make_global(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    ctx.domain_scope.make_global()

    alert_html = '<toast-alert type="success" dismiss-delay="3000">Part is now global — all domain assignments removed.</toast-alert>'
    dlb_html = render(request, "parts/_domains_dlb_only.html", _domain_scope_context(ctx)).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def part_apply_domain_template(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    template_id = request.POST.get("template_id")
    if template_id:
        PartDomainTemplateHandler(ctx.part, request.user).apply(int(template_id))

    alert_html = '<toast-alert type="success" dismiss-delay="3000">Domain template applied.</toast-alert>'
    dlb_html = render(request, "parts/_domains_dlb_only.html", _domain_scope_context(ctx)).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


def _domain_scope_context(ctx: PartContext) -> dict:
    assigned = ctx.domain_scope.domains()
    assigned_ids = [d.pk for d in assigned]
    return {
        "part_id": ctx.part.id,
        "domains_available": Domain.objects.exclude(pk__in=assigned_ids).order_by("name"),
        "domains_assigned": assigned,
    }


@require_http_methods(["POST"])
def part_add_gallery_image(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    uploaded = request.FILES.get("file")
    if uploaded:
        result = ctx.images.add(uploaded, caption=request.POST.get("caption", ""))
        if result.ok and result.attachment is not None:
            messages.success(request, "Image added to gallery.")
        else:
            for error in result.errors:
                messages.error(request, error)
    return redirect(reverse("part_detail", kwargs={"part_id": part_id}))


@require_http_methods(["POST"])
def part_remove_gallery_image(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    attachment_id = request.POST.get("attachment")
    if attachment_id and ctx.images.remove(attachment_id):
        messages.success(request, "Image removed from gallery.")
    else:
        messages.error(request, "Image not found in this part's gallery.")
    return redirect(reverse("part_detail", kwargs={"part_id": part_id}))


@require_http_methods(["POST"])
def part_set_primary_image(request: HttpRequest, part_id: int) -> HttpResponse:
    try:
        ctx = PartContext(part_id, actor=request.user)
    except PartNotFoundError:
        raise Http404
    attachment_id = request.POST.get("attachment")
    if attachment_id:
        try:
            ctx.images.set_primary(attachment_id)
            messages.success(request, "Primary image updated.")
        except PartImageError as exc:
            messages.error(request, str(exc))
    return redirect(reverse("part_detail", kwargs={"part_id": part_id}))


@require_http_methods(["POST"])
def part_add_comment(request: HttpRequest, part_id: int) -> HttpResponse:
    body = request.POST.get("content", "").strip()
    if body:
        PartContext(part_id, actor=request.user).documents_thread.add_comment(body)
        messages.success(request, "Comment added.")
    return redirect(safe_next_url(request, reverse("part_detail", kwargs={"part_id": part_id})))


def _struct_or_404(part_id: int) -> PartStruct:
    try:
        return PartStruct(part_id)
    except PartNotFoundError:
        raise Http404
