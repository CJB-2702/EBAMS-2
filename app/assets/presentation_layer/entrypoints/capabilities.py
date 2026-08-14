"""Capabilities — definition catalog + class/model/asset assignment screens.

Reads go through ``presentation_layer/search/capability_search``; writes go through
``CapabilityDefinitionContext`` (create, edit metadata, and class/model assignment
sets) and ``CapabilityManager`` (asset-layer set-reconcile for the per-asset and
bulk editors).
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.control_layer.adapters.capability_adaptor import (
    AssetBulkManagementAdaptor,
    AssetCapabilitiesEditAdaptor,
    CapabilityDefinitionCreateAdaptor,
    CapabilityDefinitionEditAdaptor,
)
from app.assets.control_layer.capabilities.capability_manager import CapabilityManager
from app.assets.control_layer.capability_definition_context import (
    CapabilityDefinitionContext,
    CapabilityDefinitionValidationError,
)
from app.assets.models import Asset, CapabilityDefinition
from app.assets.presentation_layer.search import capability_search as search


def _definitions():
    return CapabilityDefinition.objects.order_by("name")


@require_http_methods(["GET"])
def capability_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/capabilities/index.html")


@require_http_methods(["GET"])
def capability_definition_index(request: HttpRequest) -> HttpResponse:
    refs = search.reference_lists()
    return render(request, "assets/capabilities/definitions_list.html", {
        "definitions": search.search_capability_definitions(),
        "all_classes": refs["all_classes"],
        "all_models": refs["all_models"],
        "all_assets": refs["all_assets"],
    })


@require_http_methods(["GET"])
def capability_definition_detail(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = search.load_capability_definition_detail(definition_id)
    if definition is None:
        raise Http404
    editor = search.load_definition_assignment_editor(definition_id)
    return render(request, "assets/capabilities/definition_detail.html", {
        "definition": definition,
        "assigned_classes": editor["assigned_classes"],
        "assigned_models": editor["assigned_models"],
    })


@require_http_methods(["GET", "POST"])
def capability_definition_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = CapabilityDefinitionCreateAdaptor.from_post(request.POST)
        try:
            definition = CapabilityDefinitionContext.create(data=data, actor=request.user)
        except CapabilityDefinitionValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(request, "assets/capabilities/definition_edit.html", {
                "definition": None, "create": True,
            })
        messages.success(request, f"Capability '{definition.name}' created.")
        return redirect(reverse("capability_definition_detail", kwargs={"definition_id": definition.id}))
    return render(request, "assets/capabilities/definition_edit.html", {
        "definition": None, "create": True,
    })


@require_http_methods(["GET", "POST"])
def capability_definition_edit(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = search.load_capability_definition_detail(definition_id)
    if definition is None:
        raise Http404

    if request.method == "POST":
        data = CapabilityDefinitionEditAdaptor.from_post(request.POST)
        try:
            context = CapabilityDefinitionContext(definition_id, actor=request.user)
            context.update(data=data)
            context.set_classes(class_ids=data["assigned_class_ids"])
            context.set_models(model_ids=data["assigned_model_ids"])
        except CapabilityDefinitionValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
        else:
            messages.success(request, f"Capability '{definition.name}' updated.")
            return redirect(reverse("capability_definition_detail", kwargs={"definition_id": definition_id}))

    editor = search.load_definition_assignment_editor(definition_id)
    return render(request, "assets/capabilities/definition_edit.html", {
        "definition": definition,
        "create": False,
        "assigned_classes": editor["assigned_classes"],
        "available_classes": editor["available_classes"],
        "assigned_models": editor["assigned_models"],
        "available_models": editor["available_models"],
    })


@require_http_methods(["GET", "POST"])
def asset_bulk_management(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = search.load_capability_definition_detail(definition_id)
    if definition is None:
        raise Http404

    if request.method == "POST":
        desired = AssetBulkManagementAdaptor.from_post(request.POST)
        CapabilityManager(request.user).set_definition_assets(
            cap_def=definition, desired=desired
        )
        messages.success(request, f"Asset assignments for '{definition.name}' saved.")
        return redirect(reverse("asset_bulk_management", kwargs={"definition_id": definition_id}))

    ctx = search.load_asset_bulk_management(definition_id)
    return render(request, "assets/capabilities/asset_bulk_management.html", {
        "definition": definition, **ctx,
    })


@require_http_methods(["GET"])
def class_capability_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    domain = request.GET.get("domain", "").strip()
    definition = request.GET.get("definition", "").strip()
    is_active = request.GET.get("is_active", "").strip()
    refs = search.reference_lists()
    return render(request, "assets/capabilities/by_class.html", {
        "classes": search.search_classes_with_capabilities(
            q=q, category=category, domain=domain, definition=definition, is_active=is_active,
        ),
        "q": q, "category": category, "domain": domain,
        "definition": definition, "is_active": is_active,
        "all_categories": refs["all_categories"],
        "all_domains": refs["all_domains"],
        "definitions": _definitions(),
    })


@require_http_methods(["GET"])
def model_capability_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    asset_class = request.GET.get("asset_class", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    domain = request.GET.get("domain", "").strip()
    is_base_model = request.GET.get("is_base_model", "").strip()
    definition = request.GET.get("definition", "").strip()
    is_active = request.GET.get("is_active", "").strip()
    refs = search.reference_lists()
    return render(request, "assets/capabilities/by_model.html", {
        "models": search.search_models_with_capabilities(
            q=q, asset_class=asset_class, manufacturer=manufacturer, domain=domain,
            is_base_model=is_base_model, definition=definition, is_active=is_active,
        ),
        "q": q, "asset_class": asset_class, "manufacturer": manufacturer,
        "domain": domain, "is_base_model": is_base_model,
        "definition": definition, "is_active": is_active,
        "all_classes": refs["all_classes"],
        "all_manufacturers": refs["all_manufacturers"],
        "all_domains": refs["all_domains"],
        "definitions": _definitions(),
    })


@require_http_methods(["GET"])
def asset_capability_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    domain = request.GET.get("domain", "").strip()
    asset_class = request.GET.get("asset_class", "").strip()
    model = request.GET.get("model", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    status = request.GET.get("status", "").strip()

    selected_capabilities = request.GET.getlist("capabilities")
    if not selected_capabilities:
        single = request.GET.get("definition", "").strip()
        if single:
            selected_capabilities = [single]
    selected_ids = {int(c) for c in selected_capabilities if c.isdigit()}

    assets = search.search_assets_with_capabilities(
        q=q, domain=domain, asset_class=asset_class, model=model,
        manufacturer=manufacturer, status=status,
        capability_def_ids=list(selected_ids),
    )

    all_definitions = list(_definitions())
    refs = search.reference_lists()
    return render(request, "assets/capabilities/by_asset.html", {
        "assets": assets,
        "q": q, "domain": domain, "asset_class": asset_class, "model": model,
        "manufacturer": manufacturer, "status": status,
        "selected_capabilities": selected_capabilities,
        "selected_definitions": [d for d in all_definitions if d.id in selected_ids],
        "available_definitions": [d for d in all_definitions if d.id not in selected_ids],
        "domains": refs["all_domains"],
        "classes": refs["all_classes"],
        "models": refs["all_models"],
        "manufacturers": refs["all_manufacturers"],
        "status_choices": search.STATUS_CHOICES,
        "definitions": all_definitions,
    })


@require_http_methods(["GET"])
def asset_capabilities_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = search.load_asset_capabilities_detail(asset_id)
    if asset is None:
        raise Http404
    return render(request, "assets/capabilities/asset_capabilities_detail.html", {
        "asset": asset,
    })


@require_http_methods(["GET", "POST"])
def asset_capabilities_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    if request.method == "POST":
        asset = Asset.objects.filter(id=asset_id).first()
        if asset is None:
            raise Http404
        desired = AssetCapabilitiesEditAdaptor.from_post(request.POST)
        CapabilityManager(request.user).set_asset_capabilities(asset=asset, desired=desired)
        messages.success(request, f"Capabilities for '{asset.name}' saved.")
        return redirect(reverse("asset_capabilities_view", kwargs={"asset_id": asset_id}))

    ctx = search.load_asset_capabilities_editor(asset_id)
    if ctx is None:
        raise Http404
    return render(request, "assets/capabilities/asset_capabilities_edit.html", ctx)
