"""Configurations — templates, builder, defined modifications, applicability,
and per-asset configuration. Wired to the control layer.

Reads go through ``presentation_layer/search/configuration_search``; writes go
through the configuration managers (``ModificationManager``,
``ConfigurationTemplateManager``, ``TemplateModificationManager``,
``ModificationApplicabilityManager``) and the ``AssetConfigurationContext``
orchestrator for the per-asset save workflow.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.control_layer.adapters.configuration_adaptor import (
    ApplicabilityEditAdaptor,
    AssetConfigurationEditAdaptor,
    ConfigurationTemplateCreateAdaptor,
    ConfigurationTemplateEditAdaptor,
    DefinedModificationCreateAdaptor,
    DefinedModificationEditAdaptor,
)
from app.assets.control_layer.configurations.applicability.modification_applicability_manager import (
    ModificationApplicabilityManager,
)
from app.assets.control_layer.configurations.asset_configuration_context import (
    AssetConfigurationContext,
)
from app.assets.control_layer.configurations.configuration_template_manager import (
    ConfigurationTemplateManager,
)
from app.assets.control_layer.configurations.modification_manager import (
    ModificationManager,
)
from app.assets.control_layer.configurations.template_modification_manager import (
    TemplateModificationManager,
)
from app.assets.models import Asset, AssetModel, DefinedModification
from app.assets.models.configurations import ApplicabilityMode
from app.assets.presentation_layer.search import configuration_search as search


# ── Configurations Hub ──
@require_http_methods(["GET"])
def configurations_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/configurations/index.html", search.index_counts())


# ── Configuration templates ──
@require_http_methods(["GET"])
def config_template_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    model_id = request.GET.get("model", "").strip()
    modification_id = request.GET.get("modification", "").strip()
    labels = search.template_filter_labels(model_id, modification_id)
    return render(request, "assets/configurations/template_list.html", {
        "templates": search.search_config_templates(
            q=q, model_id=model_id, modification_id=modification_id
        ),
        "q": q,
        "model_filter": model_id,
        "modification_filter": modification_id,
        "selected_model": labels["selected_model"],
        "selected_modification": labels["selected_modification"],
        "models": AssetModel.objects.order_by("model_name"),
        "modifications": DefinedModification.objects.order_by("name"),
    })


@require_http_methods(["GET", "POST"])
def config_template_builder(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = ConfigurationTemplateCreateAdaptor.from_post(request.POST)
        model = AssetModel.objects.filter(id=data["model_id"]).first()
        if model is None:
            messages.error(request, "Select a target asset model.")
            return render(request, "assets/configurations/template_builder.html", {
                "models": AssetModel.objects.order_by("model_name"),
                "modifications": DefinedModification.objects.order_by("name"),
            })
        try:
            template = ConfigurationTemplateManager(request.user).create(
                model=model,
                name=data["name"],
                revision=data["revision"],
                description=data["description"],
            )
            TemplateModificationManager(request.user).set_modifications(
                template=template, modification_ids=data["modification_ids"]
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "assets/configurations/template_builder.html", {
                "models": AssetModel.objects.order_by("model_name"),
                "modifications": DefinedModification.objects.order_by("name"),
            })
        messages.success(request, f"Template '{template.name}' created.")
        return redirect(reverse("config_template_detail", kwargs={"template_id": template.id}))
    return render(request, "assets/configurations/template_builder.html", {
        "models": AssetModel.objects.order_by("model_name"),
        "modifications": DefinedModification.objects.order_by("name"),
    })


@require_http_methods(["GET", "POST"])
def config_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    editor = search.load_config_template_editor(template_id)
    if editor is None:
        raise Http404
    template = editor["template"]
    if request.method == "POST":
        data = ConfigurationTemplateEditAdaptor.from_post(request.POST)
        manager = ConfigurationTemplateManager(request.user)
        try:
            manager.update(
                template,
                name=data["name"],
                revision=data["revision"] or "",
                description=data["description"] or "",
            )
            if data["model_id"] and data["model_id"] != template.model_id:
                model = AssetModel.objects.filter(id=data["model_id"]).first()
                if model is not None:
                    template.model = model
                    template.updated_by = request.user
                    template.save(update_fields=["model", "updated_at", "updated_by"])
            if not data["is_active"] and template.is_active:
                manager.deactivate(template)
            tmm = TemplateModificationManager(request.user)
            tmm.set_modifications(
                template=template, modification_ids=data["modification_ids"]
            )
            tmm.set_children(template=template, children=data["children"])
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Template '{template.name}' updated.")
            return redirect(reverse("config_template_detail", kwargs={"template_id": template_id}))
    return render(request, "assets/configurations/template_form.html", editor)


@require_http_methods(["GET"])
def config_template_name_search(request: HttpRequest) -> HttpResponse:
    """Search-dropdown options for the child-configuration picker: existing template
    names as ``<li data-value="name">`` rows (the stored value is the name string)."""
    q = request.GET.get("q", "").strip()
    exclude_id = request.GET.get("exclude", "").strip()
    from app.assets.models import ConfigurationTemplate
    qs = ConfigurationTemplate.objects.order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if exclude_id.isdigit():
        qs = qs.exclude(id=int(exclude_id))
    return render(request, "assets/configurations/_template_name_options.html", {
        "templates": qs[:20],
    })


@require_http_methods(["GET"])
def config_template_detail(request: HttpRequest, template_id: int) -> HttpResponse:
    result = search.load_config_template_detail(template_id)
    if result is None:
        raise Http404
    template, asset_stats = result
    return render(request, "assets/configurations/template_detail.html", {
        "template": template, "asset_stats": asset_stats,
    })


# ── Defined modifications ──
@require_http_methods(["GET"])
def defined_modification_index(request: HttpRequest) -> HttpResponse:
    modifications = search.search_defined_modifications()

    if request.GET.get("format") == "htmx-search-results":
        q = request.GET.get("q", "").strip().lower()
        filtered = [
            m for m in modifications
            if not q or q in m.name.lower() or q in m.code.lower()
        ]
        if not filtered:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse(
            "\n".join(f'<li data-value="{m.id}">[{m.code}] {m.name}</li>' for m in filtered)
        )

    refs = search.reference_lists()
    return render(request, "assets/configurations/modification_list.html", {
        "modifications": modifications,
        "q": request.GET.get("q", "").strip(),
        "all_assets": Asset.objects.select_related("asset_class", "model").order_by("name"),
        "all_classes": refs["classes"],
        "all_models": refs["models"],
        "categories": search.modification_categories(),
    })


@require_http_methods(["GET"])
def defined_modification_detail(request: HttpRequest, modification_id: int) -> HttpResponse:
    result = search.load_defined_modification_detail(modification_id)
    if result is None:
        raise Http404
    modification, asset_count = result
    return render(request, "assets/configurations/modification_detail.html", {
        "modification": modification, "asset_count": asset_count,
    })


@require_http_methods(["GET", "POST"])
def defined_modification_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = DefinedModificationCreateAdaptor.from_post(request.POST)
        try:
            mod = ModificationManager(request.user).create_defined_modification(
                name=data["name"],
                code=data["code"],
                category=data["category"],
                description=data["description"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "assets/configurations/modification_form.html", {
                "modification": data, "create": True,
            })
        messages.success(request, f"Modification '{mod.name}' created.")
        return redirect(reverse("defined_modification_detail", kwargs={"modification_id": mod.id}))
    return render(request, "assets/configurations/modification_form.html", {
        "modification": None, "create": True,
    })


@require_http_methods(["GET", "POST"])
def defined_modification_edit(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = DefinedModification.objects.filter(id=modification_id).first()
    if mod is None:
        raise Http404
    if request.method == "POST":
        data = DefinedModificationEditAdaptor.from_post(request.POST)
        try:
            ModificationManager(request.user).update_defined_modification(
                mod,
                name=data["name"],
                category=data["category"] or "",
                description=data["description"] or "",
                is_active=data["is_active"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Modification '{mod.name}' updated.")
            return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))
    return render(request, "assets/configurations/modification_form.html", {"modification": mod})


# ── Modification applicability ──
@require_http_methods(["GET", "POST"])
def modification_applicability_edit(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = DefinedModification.objects.filter(id=modification_id).first()
    if mod is None:
        raise Http404

    if request.method == "POST":
        data = ApplicabilityEditAdaptor.from_post(request.POST)
        manager = ModificationApplicabilityManager(request.user)
        try:
            manager.set_classes(mod, data["class_ids"])
            manager.set_models(mod, data["model_ids"])
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Applicability for '{mod.name}' saved.")
            return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))

    mode = request.GET.get("mode")
    ctx = search.load_applicability_editor(modification_id, mode)
    template = (
        "assets/configurations/applicability/_editor_body.html"
        if request.headers.get("HX-Request") and request.GET.get("mode")
        else "assets/configurations/applicability/editor.html"
    )
    return render(request, template, ctx)


@require_http_methods(["POST"])
def modification_applicability_set_mode(request: HttpRequest, modification_id: int) -> HttpResponse:
    mod = DefinedModification.objects.filter(id=modification_id).first()
    if mod is None:
        raise Http404
    mode = request.POST.get("mode", "")
    try:
        manager = ModificationApplicabilityManager(request.user)
        manager.set_mode(mod, ApplicabilityMode(mode))
    except (ValueError, KeyError) as exc:
        messages.error(request, str(exc))
    else:
        label = search.MODE_META.get(mode, (mode,))[0]
        messages.success(request, f"'{mod.name}' set to {label}.")
    return redirect(reverse("defined_modification_detail", kwargs={"modification_id": modification_id}))


# ── Asset configuration (per asset) ──
@require_http_methods(["GET"])
def asset_configuration_detail(request: HttpRequest, asset_id: int) -> HttpResponse:
    result = search.load_asset_configuration_detail(asset_id)
    if result is None:
        raise Http404
    asset, configuration, children_configurations = result
    return render(request, "assets/configurations/asset_configuration_detail.html", {
        "asset": asset,
        "configuration": configuration,
        "children_configurations": children_configurations,
    })


@require_http_methods(["GET", "POST"])
def asset_configuration_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    if request.method == "POST":
        data = AssetConfigurationEditAdaptor.from_post(request.POST)
        try:
            AssetConfigurationContext(asset_id, actor=request.user).save(
                template_id=data["template_id"],
                verification_status=data["verification_status"],
                notes=data["notes"],
                modification_ids=data["modification_ids"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Configuration saved.")
            return redirect(reverse("asset_configuration_detail", kwargs={"asset_id": asset_id}))

    ctx = search.load_asset_configuration_editor(asset_id)
    if ctx is None:
        raise Http404
    return render(request, "assets/configurations/asset_configuration_edit.html", ctx)


@require_http_methods(["GET"])
def asset_configuration_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    domain = request.GET.get("domain", "").strip()
    asset_class = request.GET.get("asset_class", "").strip()
    model = request.GET.get("model", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    status = request.GET.get("status", "").strip()
    template_id = request.GET.get("template", "").strip()
    refs = search.reference_lists()
    labels = search.asset_filter_labels(asset_class, model)
    return render(request, "assets/configurations/by_asset.html", {
        "assets": search.search_assets_with_configuration(
            q=q, domain=domain, asset_class=asset_class, model=model,
            manufacturer=manufacturer, status=status, template_id=template_id,
        ),
        "q": q, "domain": domain, "asset_class": asset_class, "model": model,
        "manufacturer": manufacturer, "status": status, "template_id": template_id,
        "selected_class": labels["selected_class"],
        "selected_model": labels["selected_model"],
        "domains": refs["domains"], "classes": refs["classes"],
        "models": refs["models"], "manufacturers": refs["manufacturers"],
        "status_choices": search.STATUS_CHOICES, "templates": refs["templates"],
    })
