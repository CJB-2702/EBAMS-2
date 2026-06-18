"""Configurations — templates, builder, defined modifications, asset config (mock)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


# ── Configurations Hub ──
@require_http_methods(["GET"])
def configurations_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/configurations/index.html", {
        "templates_count": len(mock.get_config_templates()),
        "modifications_count": len(mock.get_defined_modifications()),
        "assets_count": len(mock.get_assets()),
    })


# ── Configuration templates ──
@require_http_methods(["GET"])
def config_template_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    model_id = request.GET.get("model", "").strip()
    modification_id = request.GET.get("modification", "").strip()
    
    templates = mock.get_config_templates()
    
    if q:
        templates = [t for t in templates if q in t.name.lower() or (t.description and q in t.description.lower())]
    if model_id:
        templates = [t for t in templates if t.model and str(t.model.id) == model_id]
    if modification_id:
        templates = [t for t in templates if any(str(m.id) == modification_id for m in t.modifications)]

    selected_model = None
    if model_id:
        selected_model = mock.get_model(model_id)
        
    selected_modification = None
    if modification_id:
        selected_modification = mock.get_defined_modification(modification_id)

    return render(request, "assets/configurations/template_list.html", {
        "templates": templates, 
        "q": request.GET.get("q", "").strip(),
        "model_filter": model_id,
        "selected_model": selected_model,
        "modification_filter": modification_id,
        "selected_modification": selected_modification,
        "models": mock.ASSET_MODELS, 
        "modifications": mock.get_defined_modifications(),
    })


@require_http_methods(["GET", "POST"])
def config_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    template = mock.get_config_template(template_id)
    if template is None:
        raise Http404
    if request.method == "POST":
        messages.success(request, f"Template '{template.name}' updated (mock — not persisted).")
        return redirect(reverse("config_template_detail", kwargs={"template_id": template_id}))
    all_mods = mock.get_defined_modifications()
    assigned_ids = {m.id for m in template.modifications}
    return render(request, "assets/configurations/template_form.html", {
        "template": template,
        "models": mock.ASSET_MODELS,
        "modifications_available": [m for m in all_mods if m.id not in assigned_ids],
        "modifications_selected": [m for m in all_mods if m.id in assigned_ids],
    })


@require_http_methods(["GET", "POST"])
def config_template_builder(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Configuration template saved (mock — not persisted).")
        return redirect(reverse("config_template_index"))
    return render(request, "assets/configurations/template_builder.html", {
        "models": mock.ASSET_MODELS, "modifications": mock.get_defined_modifications(),
    })


@require_http_methods(["GET"])
def config_template_detail(request: HttpRequest, template_id: int) -> HttpResponse:
    template = mock.get_config_template(template_id)
    if template is None:
        raise Http404
    return render(request, "assets/configurations/template_detail.html", {
        "template": template,
        "asset_stats": mock.count_template_asset_assignments(template_id),
    })


# ── Defined modifications ──
@require_http_methods(["GET"])
def defined_modification_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    modifications = mock.get_defined_modifications()
    if q:
        modifications = [m for m in modifications if q in m.name.lower() or q in m.code.lower()]
        
    if request.GET.get("format") == "htmx-search-results":
        results = [
            f'<li data-value="{m.id}">[{m.code}] {m.name}</li>'
            for m in modifications
        ]
        if not results:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse("\n".join(results))

    return render(request, "assets/configurations/modification_list.html", {
        "modifications": modifications, "q": request.GET.get("q", "").strip(),
    })


@require_http_methods(["GET"])
def defined_modification_detail(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = mock.get_defined_modification(modification_id)
    if mod is None:
        raise Http404
    return render(request, "assets/configurations/modification_detail.html", {
        "modification": mod,
        "asset_count": mock.count_modification_asset_assignments(modification_id),
    })


@require_http_methods(["GET", "POST"])
def defined_modification_edit(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = mock.get_defined_modification(modification_id)
    if mod is None:
        raise Http404
    if request.method == "POST":
        messages.success(request, f"Modification '{mod.name}' updated (mock — not persisted).")
        return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))
    return render(request, "assets/configurations/modification_form.html", {"modification": mod})


# ── Modification applicability (Phase 1) ──
def _applicability_editor_context(mod, mode: str) -> dict:
    """Split classes/models into selected vs available for the dual-listboxes,
    in the shape the chosen mode binds. Mirrors the real authoring surface."""
    selected_class_ids = (
        mock.mock_derive_classes(mod.applicable_models) if mode == "model_set"
        else list(mod.applicable_classes)
    )
    selected_model_ids = list(mod.applicable_models)
    class_options = mock.get_asset_class_options()
    model_options = mock.get_asset_model_options()
    return {
        "modification": mod,
        "mode": mode,
        "applicability": mock.applicability_ns(mode, selected_class_ids, selected_model_ids),
        "classes_selected": [c for c in class_options if c.id in selected_class_ids],
        "classes_available": [c for c in class_options if c.id not in selected_class_ids],
        "models_selected": [m for m in model_options if m.id in selected_model_ids],
        "models_available": [m for m in model_options if m.id not in selected_model_ids],
        "preview": mock.applicability_preview(mode, selected_class_ids, selected_model_ids),
        "mode_choices": [(v, mock.MODE_META[v][0]) for v in mock.APPLICABILITY_MODES],
        "model_class_map": {m.id: m.asset_class for m in model_options},
        "preview_assets": mock.preview_asset_rows(),
    }


@require_http_methods(["GET", "POST"])
def modification_applicability_edit(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = mock.get_defined_modification(modification_id)
    if mod is None:
        raise Http404
    if request.method == "POST":
        messages.success(request, f"Applicability for '{mod.name}' saved (mock — not persisted).")
        return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))
    # The mode selector reshapes the panels via hx-get ?mode=… (also F5-safe).
    mode = request.GET.get("mode") or mod.applicability.mode
    if mode not in mock.APPLICABILITY_MODES:
        mode = mod.applicability.mode
    ctx = _applicability_editor_context(mod, mode)
    template = (
        "assets/configurations/applicability/_editor_body.html"
        if request.headers.get("HX-Request") and request.GET.get("mode")
        else "assets/configurations/applicability/editor.html"
    )
    return render(request, template, ctx)


@require_http_methods(["POST"])
def modification_applicability_set_mode(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = mock.get_defined_modification(modification_id)
    if mod is None:
        raise Http404
    mode = request.POST.get("mode", "")
    label = mock.MODE_META.get(mode, (mode,))[0]
    messages.success(request, f"'{mod.name}' set to {label} (mock — not persisted).")
    return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))


@require_http_methods(["GET", "POST"])
def defined_modification_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Modification created (mock — not persisted).")
        return redirect(reverse("defined_modification_index"))
    return render(request, "assets/configurations/modification_form.html", {"modification": None, "create": True})


# ── Asset configuration (per asset) ──
@require_http_methods(["GET"])
def asset_configuration_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = mock.get_asset(asset_id)
    if asset is None:
        raise Http404
    return render(request, "assets/configurations/asset_configuration_detail.html", {
        "asset": asset, "configuration": asset.configuration,
    })


@require_http_methods(["GET", "POST"])
def asset_configuration_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = mock.get_asset(asset_id)
    if asset is None:
        raise Http404
    if request.method == "POST":
        messages.success(request, f"Configuration for '{asset.name}' saved (mock — not persisted).")
        return redirect(reverse("asset_configuration_detail", kwargs={"asset_id": asset_id}))
    configuration = asset.configuration
    assigned_ids = {am.modification.id for am in (configuration.actual_modifications if configuration else [])}
    all_mods = mock.get_defined_modifications()
    modifications_available = [m for m in all_mods if m.id not in assigned_ids]
    # Gate each candidate against THIS asset's class/model (mirrors the runtime
    # ModificationApplicabilityValidator). Forbidden rows are shown but un-addable.
    for m in modifications_available:
        ap = m.applicability
        allowed, reason = mock.mock_is_allowed(
            ap.mode, ap.class_ids, ap.model_ids,
            asset_class_id=asset.asset_class.id, asset_model_id=asset.model.id,
        )
        m.allowed = allowed
        m.block_reason = reason
    modifications_blocked = [m for m in modifications_available if not m.allowed]
    modifications_assigned = [am.modification for am in (configuration.actual_modifications if configuration else [])]
    return render(request, "assets/configurations/asset_configuration_edit.html", {
        "asset": asset, "configuration": configuration,
        "templates": mock.get_config_templates(),
        "modifications_available": modifications_available,
        "modifications_blocked": modifications_blocked,
        "modifications_assigned": modifications_assigned,
        "asset_class_options": mock.get_asset_class_options(),
        "model_options": mock.get_asset_model_options(),
    })
