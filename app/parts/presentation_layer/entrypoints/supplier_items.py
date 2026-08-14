"""Supplier item mapping + detail. Supply work portal."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.supplier_item_create_adaptor import (
    SupplierItemCreateAdaptor,
    VendorRevisionRecordAdaptor,
)
from app.parts.control_layer.domain_structs.part_structs.part_sourcing_struct import (
    PartSourcingStruct,
)
from app.parts.control_layer.domain_structs.reverse_structs.supplier_item_struct import (
    SupplierItemNotFoundError,
)
from app.parts.control_layer.managers.supplier_item_manager import (
    SupplierItemManager,
    SupplierItemValidationError,
)
from app.parts.control_layer.managers.supplier_vendor_revision_manager import (
    SupplierVendorRevisionManager,
)
from app.parts.control_layer.supplier_item_context import SupplierItemContext
from app.parts.presentation_layer.search.supplier_item_search import (
    search_supplier_items,
)
from app.utils.safe_redirect import safe_next_url

# Managing a supplier item (editing its identity/compatibility) is gated behind
# the standard Django capability for this model.
SUPPLIER_ITEM_MANAGE_PERM = "parts.change_supplieritem"


@require_http_methods(["GET"])
def supplier_items_hub(request: HttpRequest) -> HttpResponse:
    filters = {
        key: request.GET.get(key, "").strip()
        for key in ("mpn", "name", "manufacturer", "part_number")
    }
    supplier_items = search_supplier_items(**filters)
    return render(request, "parts/supplier_items/hub.html", {"supplier_items": supplier_items, **filters})


@require_http_methods(["GET"])
def part_supplier_items(request: HttpRequest, part_id: int) -> HttpResponse:
    from app.parts.control_layer.part_context import PartContext

    ctx = PartContext(part_id, actor=request.user)
    supplier_items = PartSourcingStruct.from_id(part_id, eager_thread=True).supplier_items()
    return render(
        request,
        "parts/supplier_items/by_part.html",
        {
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "supplier_items": supplier_items,
            "domains": Domain.objects.order_by("name"),
            "can_manage": request.user.has_perm(SUPPLIER_ITEM_MANAGE_PERM),
        },
    )


@require_http_methods(["GET", "POST"])
def supplier_item_create(request: HttpRequest, part_id: int) -> HttpResponse:
    from app.parts.control_layer.part_context import PartContext

    ctx = PartContext(part_id, actor=request.user)
    if request.method == "POST":
        data = SupplierItemCreateAdaptor.from_post(request.POST)
        data["internal_part_id"] = part_id
        try:
            item = SupplierItemManager.create(data=data, actor=request.user)
        except SupplierItemValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("supplier_item_create", kwargs={"part_id": part_id}))
        messages.success(request, f"Supplier item '{item.manufacturer_part_number}' mapped.")
        return redirect(reverse("part_supplier_items", kwargs={"part_id": part_id}))

    # DEV NOTE (v1 limitation): only majors/minors that already exist as PartRevision rows on
    # this Part are offered below. A future major that hasn't been created yet can't be picked,
    # and there's no custom/typed-number entry path yet. Fix later if this becomes a problem.
    revision_map: dict[str, list[int]] = {}
    for rev in ctx.revisions():
        revision_map.setdefault(str(rev.major_revision_number), []).append(
            rev.minor_revision_number
        )
    for minors in revision_map.values():
        minors.sort()
    revision_majors = sorted(revision_map.keys(), key=int)
    return render(
        request,
        "parts/supplier_items/new.html",
        {
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "revision_map": revision_map,
            "revision_majors": revision_majors,
        },
    )


@require_http_methods(["GET", "POST"])
def supplier_item_edit(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    if not request.user.has_perm(SUPPLIER_ITEM_MANAGE_PERM):
        return HttpResponseForbidden("You may not edit this supplier item.")

    part_id = ctx.item.internal_part_id
    if request.method == "POST":
        data = SupplierItemCreateAdaptor.from_post(request.POST)
        data["part_manufacturer_id"] = ctx.item.part_manufacturer_id
        data["internal_part_id"] = part_id
        try:
            ctx.update(data=data)
        except SupplierItemValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("supplier_item_edit", kwargs={"item_id": item_id}))
        messages.success(request, f"Supplier item '{ctx.item.manufacturer_part_number}' updated.")
        return redirect(reverse("part_supplier_items", kwargs={"part_id": part_id}))

    from app.parts.control_layer.part_context import PartContext

    part_ctx = PartContext(part_id, actor=request.user)
    revision_map: dict[str, list[int]] = {}
    for rev in part_ctx.revisions():
        revision_map.setdefault(str(rev.major_revision_number), []).append(
            rev.minor_revision_number
        )
    for minors in revision_map.values():
        minors.sort()
    revision_majors = sorted(revision_map.keys(), key=int)
    return render(
        request,
        "parts/supplier_items/edit.html",
        {
            "item": ctx.struct().to_dict(),
            "item_id": item_id,
            "part_id": part_id,
            "revision_map": revision_map,
            "revision_majors": revision_majors,
        },
    )


@require_http_methods(["GET"])
def supplier_item_detail(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    documents = ctx.documents()
    return render(
        request,
        "parts/supplier_items/detail.html",
        {
            "item": ctx.struct().to_dict(),
            "item_id": item_id,
            "compatibility_range": ctx.compatibility_range(),
            "vendor_revisions": ctx.vendor_revisions(),
            "image_documents": [d for d in documents if d["is_image"]],
            "other_documents": [d for d in documents if not d["is_image"]],
            "comments_card": ctx.thread.card(request.user),
            "domains": Domain.objects.order_by("name"),
            "can_manage": request.user.has_perm(SUPPLIER_ITEM_MANAGE_PERM),
        },
    )


@require_http_methods(["POST"])
def supplier_item_add_document(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    if not request.user.has_perm(SUPPLIER_ITEM_MANAGE_PERM):
        return HttpResponseForbidden("You may not add files to this supplier item.")

    uploaded_files = request.FILES.getlist("files")
    fallback_url = reverse("part_supplier_items", kwargs={"part_id": ctx.item.internal_part_id})
    if not uploaded_files:
        messages.error(request, "Choose at least one file to add.")
        return redirect(safe_next_url(request, fallback_url))

    caption = request.POST.get("caption", "").strip()
    added = 0
    for uploaded in uploaded_files:
        result = ctx.thread.attach_document(uploaded, caption=caption)
        if result.ok:
            added += 1
        else:
            for error in result.errors:
                messages.error(request, f"{uploaded.name}: {error}")
    if added:
        messages.success(request, f"{added} file{'' if added == 1 else 's'} added.")
    return redirect(safe_next_url(request, fallback_url))


@require_http_methods(["POST"])
def supplier_item_add_comment(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    body = request.POST.get("content", "").strip()
    if body:
        ctx.thread.add_comment(body)
        messages.success(request, "Comment added.")
    return redirect(
        safe_next_url(
            request,
            reverse("part_supplier_items", kwargs={"part_id": ctx.item.internal_part_id}),
        )
    )


@require_http_methods(["POST"])
def supplier_item_log_vendor_revision(request: HttpRequest, item_id: int) -> HttpResponse:
    data = VendorRevisionRecordAdaptor.from_post(request.POST)
    domain_id = request.POST.get("domain")
    if data["vendor_revision_id"] and domain_id:
        SupplierVendorRevisionManager(item_id, request.user).record(
            vendor_revision_id=data["vendor_revision_id"],
            note=data["note"],
            domain_id=int(domain_id),
        )
        messages.success(request, "Vendor revision logged.")
    return redirect(reverse("supplier_item_detail", kwargs={"item_id": item_id}))
