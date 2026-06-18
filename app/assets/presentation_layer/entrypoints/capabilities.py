"""Capabilities — definitions catalog + 3 assignment hubs (mock)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def capability_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/capabilities/index.html")


@require_http_methods(["GET"])
def capability_definition_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/capabilities/definitions_list.html", {
        "definitions": mock.get_capability_definitions(),
        "all_classes": mock.get_classes(),
        "all_models": mock.get_models(),
        "all_assets": mock.get_assets(),
    })


@require_http_methods(["GET"])
def capability_definition_detail(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = mock.get_capability_definition(definition_id)
    if definition is None:
        raise Http404
        
    all_classes = mock.get_classes()
    all_models = mock.get_models()
    
    assigned_class_ids = {r["asset_class"] for r in mock.ASSET_CLASS_CAPABILITIES if r["capability_definition"] == definition_id}
    assigned_model_ids = {r["model"] for r in mock.MODEL_CAPABILITIES if r["capability_definition"] == definition_id}
    
    assigned_classes = [c for c in all_classes if c.id in assigned_class_ids]
    assigned_models = [m for m in all_models if m.id in assigned_model_ids]
    
    return render(request, "assets/capabilities/definition_detail.html", {
        "definition": definition,
        "assigned_classes": assigned_classes,
        "assigned_models": assigned_models,
    })


@require_http_methods(["GET", "POST"])
def capability_definition_edit(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = mock.get_capability_definition(definition_id)
    if definition is None:
        raise Http404
    if request.method == "POST":
        messages.success(request, f"Capability '{definition.name}' updated (mock — not persisted).")
        return redirect(reverse("capability_definition_detail", kwargs={"definition_id": definition_id}))
        
    all_classes = mock.get_classes()
    all_models = mock.get_models()
    
    assigned_class_ids = {r["asset_class"] for r in mock.ASSET_CLASS_CAPABILITIES if r["capability_definition"] == definition_id}
    assigned_model_ids = {r["model"] for r in mock.MODEL_CAPABILITIES if r["capability_definition"] == definition_id}
    
    assigned_classes = [c for c in all_classes if c.id in assigned_class_ids]
    available_classes = [c for c in all_classes if c.id not in assigned_class_ids]
    
    assigned_models = [m for m in all_models if m.id in assigned_model_ids]
    available_models = [m for m in all_models if m.id not in assigned_model_ids]
    
    return render(request, "assets/capabilities/definition_edit.html", {
        "definition": definition,
        "assigned_classes": assigned_classes,
        "available_classes": available_classes,
        "assigned_models": assigned_models,
        "available_models": available_models,
    })


@require_http_methods(["GET", "POST"])
def asset_bulk_management(request: HttpRequest, definition_id: int) -> HttpResponse:
    definition = mock.get_capability_definition(definition_id)
    if definition is None:
        raise Http404
        
    if request.method == "POST":
        messages.success(request, f"Asset capability assignments for '{definition.name}' updated (mock — not persisted).")
        return redirect(reverse("asset_bulk_management", kwargs={"definition_id": definition_id}))
        
    all_assets = mock.get_assets()
    assigned_asset_ids = {r["asset"] for r in mock.ASSET_CAPABILITIES if r["capability_definition"] == definition_id}
    
    assigned_assets = []
    available_assets = []
    
    for a in all_assets:
        asset_obj = mock.get_asset(a.id)
        if a.id in assigned_asset_ids:
            assignment = next(r for r in mock.ASSET_CAPABILITIES if r["asset"] == a.id and r["capability_definition"] == definition_id)
            asset_obj.assignment_qty = assignment.get("qty", 1)
            asset_obj.assignment_notes = assignment.get("notes", "")
            asset_obj.assignment_is_active = assignment.get("is_active", True)
            assigned_assets.append(asset_obj)
        else:
            available_assets.append(asset_obj)
            
    assigned_class_ids = {r["asset_class"] for r in mock.ASSET_CLASS_CAPABILITIES if r["capability_definition"] == definition_id}
    assigned_model_ids = {r["model"] for r in mock.MODEL_CAPABILITIES if r["capability_definition"] == definition_id}
    
    assigned_classes = [c for c in mock.get_classes() if c.id in assigned_class_ids]
    assigned_models = [m for m in mock.get_models() if m.id in assigned_model_ids]
    
    return render(request, "assets/capabilities/asset_bulk_management.html", {
        "definition": definition,
        "assigned_assets": assigned_assets,
        "available_assets": available_assets,
        "all_classes": mock.get_classes(),
        "all_models": mock.get_models(),
        "assigned_classes": assigned_classes,
        "assigned_models": assigned_models,
    })


@require_http_methods(["GET", "POST"])
def capability_definition_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Capability definition created (mock — not persisted).")
        return redirect(reverse("capability_definition_index"))
    return render(request, "assets/capabilities/definition_detail.html", {"definition": None, "create": True})


@require_http_methods(["GET"])
def class_capability_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    category = request.GET.get("category", "").strip()
    domain = request.GET.get("domain", "").strip()
    definition = request.GET.get("definition", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    classes = mock.get_classes()

    if q:
        classes = [
            c for c in classes
            if q in c.name.lower() or (c.category and q in c.category.lower()) or (c.description and q in c.description.lower())
        ]
    if category:
        classes = [c for c in classes if c.category == category]
    if domain:
        classes = [c for c in classes if any(str(d.id) == domain for d in c.domains)]
    if definition:
        classes = [c for c in classes if any(str(cap.definition.id) == definition for cap in c.capabilities)]
    if is_active:
        classes = [c for c in classes if str(c.is_active) == is_active]

    categories = sorted(list(set(c["category"] for c in mock.ASSET_CLASSES if c.get("category"))))
    
    return render(request, "assets/capabilities/by_class.html", {
        "classes": classes,
        "q": q,
        "category": category,
        "domain": domain,
        "definition": definition,
        "is_active": is_active,
        "all_categories": categories,
        "all_domains": mock.DOMAINS,
        "definitions": mock.get_capability_definitions(),
    })


@require_http_methods(["GET"])
def model_capability_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    asset_class = request.GET.get("asset_class", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    domain = request.GET.get("domain", "").strip()
    is_base_model = request.GET.get("is_base_model", "").strip()
    definition = request.GET.get("definition", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    models = [mock._model_ns(m["id"], deep=True) for m in mock.ASSET_MODELS]

    # Resolve capability details
    for m in models:
        class_caps = [
            mock.ns(definition=mock.capdef_ns(r["capability_definition"]), is_active=r["is_active"], source="class")
            for r in mock.ASSET_CLASS_CAPABILITIES if r["asset_class"] == m.asset_class.id
        ]
        model_caps = [
            mock.ns(definition=mock.capdef_ns(r["capability_definition"]), is_active=r["is_active"], source="model")
            for r in mock.MODEL_CAPABILITIES if r["model"] == m.id
        ]
        m.class_capabilities = class_caps
        m.model_capabilities = model_caps
        m.all_capabilities = class_caps + model_caps

    if q:
        models = [m for m in models if q in m.display_name.lower()]
    if asset_class:
        models = [m for m in models if m.asset_class and str(m.asset_class.id) == asset_class]
    if manufacturer:
        models = [m for m in models if any(str(mf.id) == manufacturer for mf in m.manufacturers)]
    if domain:
        models = [m for m in models if any(str(d.id) == domain for d in m.domains)]
    if is_base_model:
        is_base = is_base_model == "True"
        models = [m for m in models if m.is_base_model == is_base]
    if definition:
        models = [m for m in models if any(str(cap.definition.id) == definition for cap in m.all_capabilities)]
    if is_active:
        models = [m for m in models if str(m.is_active) == is_active]

    return render(request, "assets/capabilities/by_model.html", {
        "models": models,
        "q": q,
        "asset_class": asset_class,
        "manufacturer": manufacturer,
        "domain": domain,
        "is_base_model": is_base_model,
        "definition": definition,
        "is_active": is_active,
        "all_classes": mock.ASSET_CLASSES,
        "all_manufacturers": mock.MANUFACTURERS,
        "all_domains": mock.DOMAINS,
        "definitions": mock.get_capability_definitions(),
    })


@require_http_methods(["GET"])
def asset_capability_index(request: HttpRequest) -> HttpResponse:
    # Deep load assets so they have resolved capabilities
    assets = [mock.get_asset(a.id) for a in mock.get_assets()]
    
    # Parse filter params
    q = request.GET.get("q", "").strip().lower()
    domain = request.GET.get("domain", "").strip()
    klass = request.GET.get("asset_class", "").strip()
    model = request.GET.get("model", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    status = request.GET.get("status", "").strip()
    
    # Allow inclusive filtering by multiple capabilities
    selected_capabilities = request.GET.getlist("capabilities")
    if not selected_capabilities:
        single_def = request.GET.get("definition", "").strip()
        if single_def:
            selected_capabilities = [single_def]
            
    # Apply filters
    if q:
        assets = [a for a in assets if q in a.name.lower() or q in a.serial_number.lower()]
    if domain:
        assets = [a for a in assets if a.domain and str(a.domain.id) == domain]
    if klass:
        assets = [a for a in assets if a.asset_class and str(a.asset_class.id) == klass]
    if model:
        assets = [a for a in assets if a.model and str(a.model.id) == model]
    if manufacturer:
        assets = [a for a in assets if any(str(m.id) == manufacturer for m in a.model.manufacturers)]
    if status:
        assets = [a for a in assets if a.status == status]
    if selected_capabilities:
        cap_ids = {int(cid) for cid in selected_capabilities if cid.isdigit()}
        assets = [
            a for a in assets
            if cap_ids.issubset({cap.definition.id for cap in a.capabilities})
        ]
        
    all_definitions = mock.get_capability_definitions()
    selected_ids = {int(cid) for cid in selected_capabilities if cid.isdigit()}
    selected_definitions = [d for d in all_definitions if d.id in selected_ids]
    available_definitions = [d for d in all_definitions if d.id not in selected_ids]

    return render(request, "assets/capabilities/by_asset.html", {
        "assets": assets,
        "q": q,
        "domain": domain,
        "asset_class": klass,
        "model": model,
        "manufacturer": manufacturer,
        "status": status,
        "selected_capabilities": selected_capabilities,
        "selected_definitions": selected_definitions,
        "available_definitions": available_definitions,
        "domains": mock.DOMAINS,
        "classes": mock.ASSET_CLASSES,
        "models": mock.get_models(),
        "manufacturers": mock.MANUFACTURERS,
        "status_choices": mock.STATUS_CHOICES,
        "definitions": all_definitions,
    })


@require_http_methods(["GET"])
def asset_capabilities_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = mock.get_asset(asset_id)
    if asset is None:
        raise Http404
    return render(request, "assets/capabilities/asset_capabilities_detail.html", {
        "asset": asset,
    })


@require_http_methods(["GET", "POST"])
def asset_capabilities_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = mock.get_asset(asset_id)
    if asset is None:
        raise Http404
        
    if request.method == "POST":
        messages.success(request, f"Capabilities for '{asset.name}' updated (mock — not persisted).")
        return redirect(reverse("asset_capabilities_view", kwargs={"asset_id": asset_id}))
        
    # Get all definitions
    all_defs = mock.get_capability_definitions()
    
    # Get directly assigned capability definitions (Asset source)
    assigned_rows = [
        mock.ns(
            id=r["id"],
            definition=mock.capdef_ns(r["capability_definition"]),
            qty=r.get("qty", 1),
            notes=r.get("notes", ""),
            is_active=r.get("is_active", True)
        )
        for r in mock.ASSET_CAPABILITIES if r["asset"] == asset.id
    ]
    
    assigned_def_ids = {r.definition.id for r in assigned_rows}
    available_defs = [d for d in all_defs if d.id not in assigned_def_ids]
    
    # Inherited from class or model (read-only references)
    inherited_caps = [
        cap for cap in asset.capabilities if cap.source in ("Class", "Model")
    ]
    
    return render(request, "assets/capabilities/asset_capabilities_edit.html", {
        "asset": asset,
        "capabilities_available": available_defs,
        "capabilities_assigned": assigned_rows,
        "capabilities_inherited": inherited_caps,
    })
