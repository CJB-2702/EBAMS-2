"""Vendor registry — list + create. Owned by procurement; unrelated to parts."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.procurement.control_layer.adapters.vendor_create_adaptor import (
    VendorCreateAdaptor,
)
from app.procurement.control_layer.managers.vendor_manager import (
    VendorManager,
    VendorValidationError,
)
from app.procurement.models import Vendor


@require_http_methods(["GET"])
def vendor_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Vendor.objects.order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if request.GET.get("is_active") == "1":
        qs = qs.filter(is_active=True)

    if request.GET.get("format") == "htmx-search-results":
        results = [f'<li data-value="{v.id}">{v.name}</li>' for v in qs[:20]]
        return HttpResponse("\n".join(results) or '<li class="is-disabled">No matches.</li>')

    return render(request, "procurement/vendors/list.html", {"vendors": qs, "q": q})


@require_http_methods(["GET", "POST"])
def vendor_create(request: HttpRequest) -> HttpResponse:
    # format=htmx-fragment is the price grid's inline "create vendor" sub-flow
    # (mirrors parts/manufacturers::manufacturer_create) — field_name/target_id
    # let any picker instance reuse this same fragment.
    fragment = request.GET.get("format") == "htmx-fragment"
    field_name = request.POST.get("field_name") or request.GET.get("field_name") or "vendor_id"
    target_id = request.POST.get("target_id") or request.GET.get("target_id") or "vendor-picker-slot"

    if request.method == "POST":
        data = (
            VendorCreateAdaptor.from_quick_create_post(request.POST)
            if fragment
            else VendorCreateAdaptor.from_post(request.POST)
        )
        try:
            vendor = VendorManager.create(data=data, actor=request.user)
        except VendorValidationError as exc:
            if fragment:
                return render(
                    request,
                    "procurement/prices/_vendor_picker.html",
                    {
                        "create_errors": exc.errors,
                        "create_data": data,
                        "show_create_form": True,
                        "field_name": field_name,
                        "target_id": target_id,
                    },
                )
            for error in exc.errors:
                messages.error(request, error)
            return render(request, "procurement/vendors/form.html", {"vendor": data})
        if fragment:
            return render(
                request,
                "procurement/prices/_vendor_picker.html",
                {"selected_vendor": vendor, "field_name": field_name, "target_id": target_id},
            )
        messages.success(request, f"Vendor '{vendor.name}' created.")
        return redirect(reverse("vendor_index"))

    if fragment:
        # GET ...?format=htmx-fragment&reset=1 — swap a selected vendor back
        # to the unselected search state.
        return render(
            request,
            "procurement/prices/_vendor_picker.html",
            {"field_name": field_name, "target_id": target_id},
        )

    return render(request, "procurement/vendors/form.html", {"vendor": None})
