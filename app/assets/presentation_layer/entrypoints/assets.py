"""Asset list / 360 detail / create / edit / images (mock — no persistence)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def asset_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    domain = request.GET.get("domain", "").strip()
    klass = request.GET.get("asset_class", "").strip()
    status = request.GET.get("status", "").strip()

    assets = mock.get_assets()
    if q:
        assets = [a for a in assets if q in a.name.lower() or q in a.serial_number.lower()]
    if domain:
        assets = [a for a in assets if a.domain and str(a.domain.id) == domain]
    if klass:
        assets = [a for a in assets if a.asset_class and str(a.asset_class.id) == klass]
    if status:
        assets = [a for a in assets if a.status == status]

    return render(request, "assets/assets/list.html", {
        "assets": assets,
        "q": q, "domain": domain, "asset_class": klass, "status": status,
        "domains": mock.DOMAINS, "classes": mock.ASSET_CLASSES,
        "models": mock.ASSET_MODELS, "manufacturers": mock.MANUFACTURERS,
        "status_choices": mock.STATUS_CHOICES,
        "capability_status_choices": mock.CAPABILITY_STATUS_CHOICES,
    })


def _get_or_404(asset_id):
    asset = mock.get_asset(asset_id)
    if asset is None:
        raise Http404
    return asset


@require_http_methods(["GET"])
def asset_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    return render(request, "assets/assets/detail.html", {"asset": _get_or_404(asset_id)})


@require_http_methods(["GET", "POST"])
def asset_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Asset created (mock — not persisted).")
        return redirect(reverse("asset_index"))
    return render(request, "assets/assets/form.html", {
        "mode": "create", "asset": None,
        "domains": mock.DOMAINS, "classes": mock.ASSET_CLASSES, "models": mock.ASSET_MODELS,
        "status_choices": mock.STATUS_CHOICES,
    })


@require_http_methods(["GET", "POST"])
def asset_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = _get_or_404(asset_id)
    if request.method == "POST":
        messages.success(request, f"Asset '{asset.name}' updated (mock — not persisted).")
        return redirect(reverse("asset_detail", kwargs={"asset_id": asset_id}))
    return render(request, "assets/assets/form.html", {
        "mode": "edit", "asset": asset,
        "domains": mock.DOMAINS, "classes": mock.ASSET_CLASSES, "models": mock.ASSET_MODELS,
        "status_choices": mock.STATUS_CHOICES,
    })


@require_http_methods(["GET", "POST"])
def asset_images(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = _get_or_404(asset_id)
    if request.method == "POST":
        messages.success(request, "Image gallery updated (mock — not persisted).")
        return redirect(reverse("asset_images", kwargs={"asset_id": asset_id}))
    return render(request, "assets/assets/images.html", {"asset": asset})


@require_http_methods(["GET", "POST"])
def asset_hierarchy_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = _get_or_404(asset_id)
    if request.method == "POST":
        messages.success(request, "Asset hierarchy updated (mock — not persisted).")
        return redirect(reverse("asset_detail", kwargs={"asset_id": asset_id}))
    # Get potential parents (all assets except self)
    all_assets = [a for a in mock.get_assets() if a.id != asset.id]
    return render(request, "assets/assets/hierarchy_edit.html", {"asset": asset, "all_assets": all_assets})


@require_http_methods(["GET", "POST"])
def asset_meter_history(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = _get_or_404(asset_id)
    if request.method == "POST":
        messages.success(request, "Meter reading added (mock — not persisted).")
        return redirect(reverse("asset_meter_history", kwargs={"asset_id": asset_id}))
    
    # Filter meter history for this specific asset
    history = [r for r in mock.get_meter_history() if r.asset.id == asset.id]
    
    return render(request, "assets/assets/meter_history.html", {"asset": asset, "history": history})
