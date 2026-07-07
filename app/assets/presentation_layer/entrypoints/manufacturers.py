"""Manufacturer list / detail / create / edit — wired to the control layer.

Reads go through ``presentation_layer/search``; writes go through the
``ManufacturerFactory`` (create) and ``ManufacturerContext`` (edit). The
entrypoint stays a thin traffic controller: adapt the payload, call control,
redirect.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.control_layer.adapters.manufacturer_adaptor import (
    ManufacturerCreateAdaptor,
    ManufacturerEditAdaptor,
)
from app.assets.control_layer.factories.manufacturer_factory import (
    ManufacturerFactory,
    ManufacturerValidationError,
)
from app.assets.control_layer.manufacturer_context import (
    ManufacturerContext,
    ManufacturerValidationError as ManufacturerEditValidationError,
)
from app.assets.presentation_layer.search.manufacturer_search import (
    load_manufacturer_detail,
    search_manufacturers,
)


@require_http_methods(["GET"])
def manufacturer_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    is_active = request.GET.get("is_active", "").strip()
    rows = search_manufacturers(q=q, is_active=is_active)
    return render(
        request,
        "assets/manufacturers/list.html",
        {"manufacturers": rows, "q": q, "is_active": is_active},
    )


def _get_or_404(manufacturer_id: int):
    manufacturer = load_manufacturer_detail(manufacturer_id)
    if manufacturer is None:
        raise Http404
    return manufacturer


@require_http_methods(["GET"])
def manufacturer_detail(request: HttpRequest, manufacturer_id: int) -> HttpResponse:
    return render(
        request,
        "assets/manufacturers/detail.html",
        {"manufacturer": _get_or_404(manufacturer_id)},
    )


@require_http_methods(["GET", "POST"])
def manufacturer_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = ManufacturerCreateAdaptor.from_post(request.POST)
        try:
            manufacturer = ManufacturerFactory.create(data=data, actor=request.user)
        except ManufacturerValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/manufacturers/form.html",
                {"mode": "create", "manufacturer": data},
            )
        messages.success(request, f"Manufacturer '{manufacturer.name}' created.")
        return redirect(
            reverse("manufacturer_detail", kwargs={"manufacturer_id": manufacturer.id})
        )
    return render(
        request,
        "assets/manufacturers/form.html",
        {"mode": "create", "manufacturer": None},
    )


@require_http_methods(["GET", "POST"])
def manufacturer_edit(request: HttpRequest, manufacturer_id: int) -> HttpResponse:
    manufacturer = _get_or_404(manufacturer_id)
    if request.method == "POST":
        data = ManufacturerEditAdaptor.from_post(request.POST)
        try:
            context = ManufacturerContext(manufacturer_id, actor=request.user)
            manufacturer = context.update(data=data)
        except ManufacturerEditValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/manufacturers/form.html",
                {"mode": "edit", "manufacturer": manufacturer},
            )
        messages.success(request, f"Manufacturer '{manufacturer.name}' updated.")
        return redirect(
            reverse("manufacturer_detail", kwargs={"manufacturer_id": manufacturer.id})
        )
    return render(
        request,
        "assets/manufacturers/form.html",
        {"mode": "edit", "manufacturer": manufacturer},
    )
