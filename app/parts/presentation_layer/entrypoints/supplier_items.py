"""Supplier item mapping + detail. Supply work portal."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.supplier_item_create_adaptor import (
    SupplierItemCreateAdaptor,
    VendorRevisionRecordAdaptor,
)
from app.parts.control_layer.domain_structs.supplier_item_struct import (
    SupplierItemNotFoundError,
)
from app.parts.control_layer.factories.supplier_item_factory import (
    SupplierItemFactory,
    SupplierItemValidationError,
)
from app.parts.control_layer.managers.part_thread_manager import PartThreadManager
from app.parts.control_layer.managers.supplier_vendor_revision_manager import (
    SupplierVendorRevisionManager,
)
from app.parts.control_layer.supplier_item_context import SupplierItemContext
from app.parts.models import PartManufacturer


@require_http_methods(["GET", "POST"])
def part_supplier_items(request: HttpRequest, part_id: int) -> HttpResponse:
    from app.parts.control_layer.part_context import PartContext

    ctx = PartContext(part_id, actor=request.user)
    if request.method == "POST":
        data = SupplierItemCreateAdaptor.from_post(request.POST)
        data["internal_part_id"] = part_id
        try:
            item = SupplierItemFactory.create(data=data, actor=request.user)
        except SupplierItemValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return redirect(reverse("part_supplier_items", kwargs={"part_id": part_id}))
        messages.success(request, f"Supplier item '{item.manufacturer_part_number}' mapped.")
        return redirect(reverse("part_supplier_items", kwargs={"part_id": part_id}))
    supplier_items = []
    for s in ctx.supplier_items():
        data = s.to_dict()
        thread = PartThreadManager(s.item, request.user)
        docs = thread.documents()
        data["image_documents"] = [d for d in docs if d["is_image"]]
        data["other_documents"] = [d for d in docs if not d["is_image"]]
        data["comments"] = thread.comments()
        supplier_items.append(data)
    return render(
        request,
        "parts/supplier_items/by_part.html",
        {
            "part": ctx.struct().to_dict(),
            "part_id": part_id,
            "supplier_items": supplier_items,
            "manufacturers": PartManufacturer.objects.filter(is_active=True).order_by("name"),
            "domains": Domain.objects.order_by("name"),
        },
    )


@require_http_methods(["GET"])
def supplier_item_detail(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    return render(
        request,
        "parts/supplier_items/detail.html",
        {
            "item": ctx.struct().to_dict(),
            "item_id": item_id,
            "compatibility_range": ctx.compatibility_range(),
            "vendor_revisions": ctx.vendor_revisions(),
            "documents": ctx.documents(),
            "comments": ctx.comments(),
            "domains": Domain.objects.order_by("name"),
        },
    )


@require_http_methods(["POST"])
def supplier_item_add_comment(request: HttpRequest, item_id: int) -> HttpResponse:
    try:
        ctx = SupplierItemContext(item_id, actor=request.user)
    except SupplierItemNotFoundError:
        raise Http404
    body = request.POST.get("body", "").strip()
    domain_id = request.POST.get("domain")
    if body and domain_id:
        ctx.thread.add_comment(body, domain_id=int(domain_id))
        messages.success(request, "Comment added.")
    return redirect(
        reverse("part_supplier_items", kwargs={"part_id": ctx.item.internal_part_id})
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
