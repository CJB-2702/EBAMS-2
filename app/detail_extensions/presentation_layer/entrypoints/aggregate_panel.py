"""Aggregate 360-panel entrypoint.

GET /detail_extensions/asset/<id>/?format=htmx-panel  → card strip for one asset
GET /detail_extensions/model/<id>/?format=htmx-panel  → card strip for one model

Supports both HTMX fragment mode (format=htmx-panel) and a full-page F5 reload.
Read-only; no writes.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from app.assets.models import Asset, AssetModel
from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import ExtensionTarget
from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)


def _enabled_asset_extensions(asset: "Asset") -> list:
    """Return descriptors of extensions enabled for this asset (class or model scope)."""
    class_keys = set(
        DetailExtensionsByAssetClass.objects.filter(
            asset_class_id=asset.asset_class_id,
            extension_key__in=list(registry.EXTENSION_REGISTRY),
        ).values_list("extension_key", flat=True)
    )
    model_keys = set(
        DetailExtensionsByModel.objects.filter(
            model_id=asset.model_id,
            extension_key__in=list(registry.EXTENSION_REGISTRY),
        ).values_list("extension_key", flat=True)
    )
    all_keys = class_keys | model_keys
    return [
        registry.EXTENSION_REGISTRY[k]
        for k in all_keys
        if k in registry.EXTENSION_REGISTRY and registry.EXTENSION_REGISTRY[k].target is ExtensionTarget.ASSET
    ]


def _enabled_model_extensions(model: "AssetModel") -> list:
    """Return descriptors of extensions enabled for this model (class scope)."""
    class_keys = set(
        ModelDetailExtensionsByAssetClass.objects.filter(
            asset_class_id=model.asset_class_id,
            extension_key__in=list(registry.EXTENSION_REGISTRY),
        ).values_list("extension_key", flat=True)
    )
    return [
        registry.EXTENSION_REGISTRY[k]
        for k in class_keys
        if k in registry.EXTENSION_REGISTRY and registry.EXTENSION_REGISTRY[k].target is ExtensionTarget.MODEL
    ]


@require_http_methods(["GET"])
def panel(request: HttpRequest, owner_type: str, owner_id: int) -> HttpResponse:
    if owner_type not in ("asset", "model"):
        raise Http404(f"Unknown owner type: {owner_type!r}")

    if owner_type == "asset":
        owner = get_object_or_404(Asset.objects.select_related("asset_class", "model"), pk=owner_id)
        descriptors = _enabled_asset_extensions(owner)
    else:
        owner = get_object_or_404(AssetModel.objects.select_related("asset_class"), pk=owner_id)
        descriptors = _enabled_model_extensions(owner)

    fmt = request.GET.get("format", "")
    template = (
        "detail_extensions/panel/panel_fragment.html"
        if fmt == "htmx-panel"
        else "detail_extensions/panel/panel.html"
    )

    return render(
        request,
        template,
        {
            "owner": owner,
            "owner_type": owner_type,
            "descriptors": descriptors,
        },
    )
