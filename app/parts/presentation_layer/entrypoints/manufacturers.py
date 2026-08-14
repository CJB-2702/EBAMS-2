"""Part Manufacturer registry — list + create. Supply / Sourcing work portal."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.parts.control_layer.adapters.manufacturer_create_adaptor import (
    ManufacturerCreateAdaptor,
)
from app.parts.control_layer.managers.part_manufacturer_manager import (
    PartManufacturerManager,
    PartManufacturerValidationError,
)
from app.parts.models import PartManufacturer


@require_http_methods(["GET"])
def manufacturer_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = PartManufacturer.objects.order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if request.GET.get("is_active") == "1":
        qs = qs.filter(is_active=True)

    if request.GET.get("format") == "htmx-search-results":
        results = [f'<li data-value="{m.id}">{m.name}</li>' for m in qs[:20]]
        return HttpResponse("\n".join(results) or '<li class="is-disabled">No matches.</li>')

    return render(request, "parts/manufacturers/list.html", {"manufacturers": qs, "q": q})


@require_http_methods(["GET", "POST"])
def manufacturer_create(request: HttpRequest) -> HttpResponse:
    # format=htmx-fragment is a wizard's inline "create manufacturer" sub-flow — the one
    # legitimate server round trip inside an otherwise client-side wizard, because a
    # PartManufacturer needs a real DB id before the rest of the wizard's form can reference it.
    # field_name/target_id let repeatable-row wizards (the part-creation wizard) reuse this same
    # fragment per row; single-row callers (the supplier-item wizard) rely on the defaults.
    fragment = request.GET.get("format") == "htmx-fragment"
    field_name = request.POST.get("field_name") or request.GET.get("field_name") or "part_manufacturer_id"
    target_id = request.POST.get("target_id") or request.GET.get("target_id") or "supplier-item-manufacturer-slot"

    if request.method == "POST":
        data = (
            ManufacturerCreateAdaptor.from_quick_create_post(request.POST)
            if fragment
            else ManufacturerCreateAdaptor.from_post(request.POST)
        )
        try:
            manufacturer = PartManufacturerManager.create(data=data, actor=request.user)
        except PartManufacturerValidationError as exc:
            if fragment:
                return render(
                    request,
                    "parts/manufacturers/_manufacturer_picker.html",
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
            return render(
                request, "parts/manufacturers/form.html", {"manufacturer": data}
            )
        if fragment:
            return render(
                request,
                "parts/manufacturers/_manufacturer_picker.html",
                {
                    "selected_manufacturer": manufacturer,
                    "field_name": field_name,
                    "target_id": target_id,
                },
            )
        messages.success(request, f"Manufacturer '{manufacturer.name}' created.")
        return redirect(reverse("part_manufacturer_index"))

    if fragment:
        # GET ...?format=htmx-fragment&reset=1 — the wizard's "Change" link swaps a selected
        # manufacturer back to the unselected search state.
        return render(
            request,
            "parts/manufacturers/_manufacturer_picker.html",
            {"field_name": field_name, "target_id": target_id},
        )

    return render(request, "parts/manufacturers/form.html", {"manufacturer": None})
