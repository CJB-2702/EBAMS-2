"""Asset list / 360 detail / create / edit / images / hierarchy / meters —
wired to the control layer.

Creation goes through ``AssetCreationOrchestrator`` (which builds the required
photo-gallery + documentation threads, emits the lifecycle event, and copies model
capabilities). All edits/sub-actions go through ``AssetContext`` and its managers
(metadata, meters, hierarchy, images). Reads go through ``search/asset_search``.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.control_layer.adapters.asset_create_adaptor import AssetCreateAdaptor
from app.assets.control_layer.asset_context import (
    AssetContext,
    AssetValidationError as AssetEditValidationError,
)
from app.assets.control_layer.factories.asset_factory import AssetValidationError
from app.assets.control_layer.guards.relationship_guard import RelationshipError
from app.assets.control_layer.managers.asset_hierarchy_manager import HierarchyError
from app.assets.control_layer.managers.asset_image_manager import AssetImageError
from app.assets.control_layer.orchestrators.asset_creation_orchestrator import (
    AssetCreationOrchestrator,
)
from app.assets.models import AssetClass, AssetModel, Manufacturer
from app.assets.presentation_layer.search.asset_search import (
    build_meter_rows,
    load_asset_base,
    load_asset_detail,
    load_meter_history,
    search_assets,
)

STATUS_CHOICES = ["Active", "Inactive", "Maintenance", "Retired", "Disposed"]
CAPABILITY_STATUS_CHOICES = ["Operational", "Degraded", "Down", "Unknown"]


def _form_choices() -> dict:
    return {
        "domains": Domain.objects.order_by("name"),
        "classes": AssetClass.objects.order_by("name"),
        "models": AssetModel.objects.order_by("model_name", "subtype_name"),
        "manufacturers": Manufacturer.objects.order_by("name"),
        "status_choices": STATUS_CHOICES,
        "capability_status_choices": CAPABILITY_STATUS_CHOICES,
    }


def _parse_tags(post) -> list[str]:
    raw = post.get("tags", "") or ""
    return [t.strip() for t in raw.split(",") if t.strip()]


def _parse_meter_readings(post) -> dict[int, float]:
    readings: dict[int, float] = {}
    for index in range(1, 5):
        raw = post.get(f"meter{index}")
        if raw not in (None, ""):
            try:
                readings[index] = float(raw)
            except (TypeError, ValueError):
                continue
    return readings


@require_http_methods(["GET"])
def asset_index(request: HttpRequest) -> HttpResponse:
    filters = {
        key: request.GET.get(key, "").strip()
        for key in (
            "q", "domain", "asset_class", "model",
            "manufacturer", "status", "capability_status",
        )
    }
    assets = search_assets(**filters)
    return render(
        request,
        "assets/assets/list.html",
        {"assets": assets, **filters, **_form_choices()},
    )


@require_http_methods(["GET"])
def asset_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    bundle = load_asset_detail(asset_id)
    if bundle is None:
        raise Http404
    return render(request, "assets/assets/detail.html", bundle)


@require_http_methods(["GET", "POST"])
def asset_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = AssetCreateAdaptor.from_post(request.POST)
        try:
            asset = AssetCreationOrchestrator.create(data=data, actor=request.user)
        except AssetValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/assets/form.html",
                {"mode": "create", "asset": data, **_form_choices()},
            )
        # Apply form extras the orchestrator does not own: tags + initial meters.
        context = AssetContext(asset.id, actor=request.user)
        context.update(data={"tags": _parse_tags(request.POST)})
        readings = _parse_meter_readings(request.POST)
        if readings:
            context.record_meters(readings, source="create")
        messages.success(request, f"Asset '{asset.name}' created.")
        return redirect(reverse("asset_detail", kwargs={"asset_id": asset.id}))
    return render(
        request,
        "assets/assets/form.html",
        {"mode": "create", "asset": None, **_form_choices()},
    )


@require_http_methods(["GET", "POST"])
def asset_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    if request.method == "POST":
        context = AssetContext(asset_id, actor=request.user)
        try:
            context.update(
                data={
                    "name": request.POST.get("name", ""),
                    "serial_number": request.POST.get("serial_number", ""),
                    "status": request.POST.get("status", "") or "Active",
                    "tags": _parse_tags(request.POST),
                }
            )
            readings = _parse_meter_readings(request.POST)
            if readings:
                context.record_meters(readings, source="edit")
        except AssetEditValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/assets/form.html",
                {"mode": "edit", "asset": asset, **_form_choices()},
            )
        messages.success(request, f"Asset '{context.asset.name}' updated.")
        return redirect(reverse("asset_detail", kwargs={"asset_id": asset_id}))
    return render(
        request,
        "assets/assets/form.html",
        {"mode": "edit", "asset": asset, **_form_choices()},
    )


@require_http_methods(["GET", "POST"])
def asset_images(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    if request.method == "POST":
        context = AssetContext(asset_id, actor=request.user)
        try:
            if request.POST.get("delete"):
                context.images.delete_image(int(request.POST["delete"]))
                messages.success(request, "Image deleted.")
            elif request.POST.get("set_primary"):
                context.images.set_primary(int(request.POST["set_primary"]))
                messages.success(request, "Primary image updated.")
            elif request.FILES.get("image"):
                context.images.add_image(request.FILES["image"])
                messages.success(request, "Image uploaded.")
            else:
                messages.error(request, "Choose an image to upload.")
        except (AssetImageError, ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("asset_images", kwargs={"asset_id": asset_id}))

    images = list(asset.images.select_related("attachment").all())
    return render(
        request, "assets/assets/images.html", {"asset": asset, "images": images}
    )


@require_http_methods(["GET", "POST"])
def asset_hierarchy_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    if request.method == "POST":
        raw = request.POST.get("parent_id", "").strip()
        new_parent_id = int(raw) if raw else None
        try:
            AssetContext(asset_id, actor=request.user).reparent(new_parent_id)
            messages.success(request, "Asset hierarchy updated.")
        except (RelationshipError, HierarchyError, ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("asset_detail", kwargs={"asset_id": asset_id}))

    # The dedicated relationship surface supersedes the legacy hierarchy editor.
    return redirect(reverse("children_edit", kwargs={"asset_id": asset_id}))


@require_http_methods(["GET", "POST"])
def asset_meter_history(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    if request.method == "POST":
        context = AssetContext(asset_id, actor=request.user)
        try:
            index = int(request.POST.get("meter_index", "0"))
            value = float(request.POST.get("value"))
        except (TypeError, ValueError):
            messages.error(request, "A meter and numeric value are required.")
            return redirect(reverse("asset_meter_history", kwargs={"asset_id": asset_id}))
        recorded_raw = request.POST.get("recorded_at", "")
        recorded_at = parse_datetime(recorded_raw) if recorded_raw else None
        if recorded_at is not None and timezone.is_naive(recorded_at):
            recorded_at = timezone.make_aware(recorded_at)
        try:
            context.record_meters(
                {index: value},
                recorded_at=recorded_at or timezone.now(),
                source="manual",
            )
            messages.success(request, "Meter reading recorded.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("asset_meter_history", kwargs={"asset_id": asset_id}))

    return render(
        request,
        "assets/assets/meter_history.html",
        {
            "asset": asset,
            "meters": build_meter_rows(asset),
            "history": load_meter_history(asset),
        },
    )
