"""Manufacturer list / detail / create / edit (mock — NEW resource)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def manufacturer_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    rows = mock.get_manufacturers()
    if q:
        rows = [m for m in rows if q in m.name.lower() or (m.code and q in m.code.lower())]
    return render(request, "assets/manufacturers/list.html", {"manufacturers": rows, "q": q})


def _get_or_404(mid):
    m = mock.get_manufacturer(mid)
    if m is None:
        raise Http404
    return m


@require_http_methods(["GET"])
def manufacturer_detail(request: HttpRequest, manufacturer_id: int) -> HttpResponse:
    return render(request, "assets/manufacturers/detail.html", {"manufacturer": _get_or_404(manufacturer_id)})


@require_http_methods(["GET", "POST"])
def manufacturer_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Manufacturer created (mock — not persisted).")
        return redirect(reverse("manufacturer_index"))
    return render(request, "assets/manufacturers/form.html", {"mode": "create", "manufacturer": None})


@require_http_methods(["GET", "POST"])
def manufacturer_edit(request: HttpRequest, manufacturer_id: int) -> HttpResponse:
    m = _get_or_404(manufacturer_id)
    if request.method == "POST":
        messages.success(request, f"Manufacturer '{m.name}' updated (mock — not persisted).")
        return redirect(reverse("manufacturer_detail", kwargs={"manufacturer_id": manufacturer_id}))
    return render(request, "assets/manufacturers/form.html", {"mode": "edit", "manufacturer": m})
