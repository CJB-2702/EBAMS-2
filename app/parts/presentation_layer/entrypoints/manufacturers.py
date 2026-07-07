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
from app.parts.control_layer.factories.part_manufacturer_factory import (
    PartManufacturerFactory,
    PartManufacturerValidationError,
)
from app.parts.models import PartManufacturer


@require_http_methods(["GET"])
def manufacturer_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = PartManufacturer.objects.order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(request, "parts/manufacturers/list.html", {"manufacturers": qs, "q": q})


@require_http_methods(["GET", "POST"])
def manufacturer_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = ManufacturerCreateAdaptor.from_post(request.POST)
        try:
            manufacturer = PartManufacturerFactory.create(data=data, actor=request.user)
        except PartManufacturerValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request, "parts/manufacturers/form.html", {"manufacturer": data}
            )
        messages.success(request, f"Manufacturer '{manufacturer.name}' created.")
        return redirect(reverse("part_manufacturer_index"))
    return render(request, "parts/manufacturers/form.html", {"manufacturer": None})
