"""Asset Model list / detail / create / edit — wired to the control layer.

Reads go through ``presentation_layer/search``; creation through
``AssetModelFactory`` (which also copies class capability templates and emits the
lifecycle event); edits through ``AssetModelContext`` (metadata, meter units,
asset-class propagation, manufacturer set, declared capability set).
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.control_layer.adapters.asset_model_adaptor import (
    AssetModelCreateAdaptor,
    AssetModelEditAdaptor,
)
from app.assets.control_layer.asset_model_context import AssetModelContext
from app.assets.control_layer.factories.asset_model_factory import (
    AssetModelFactory,
    AssetModelValidationError,
)
from app.assets.models import AssetClass, CapabilityDefinition, Manufacturer
from app.assets.presentation_layer.search.asset_model_search import (
    load_model_detail,
    search_models,
)


def _form_choices() -> dict:
    return {
        "classes": AssetClass.objects.order_by("name"),
        "manufacturers": Manufacturer.objects.order_by("name"),
        "domains": Domain.objects.order_by("name"),
    }


@require_http_methods(["GET"])
def model_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    asset_class = request.GET.get("asset_class", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    domain = request.GET.get("domain", "").strip()
    is_base_model = request.GET.get("is_base_model", "").strip()

    models = search_models(
        q=q,
        asset_class=asset_class,
        manufacturer=manufacturer,
        domain=domain,
        is_base_model=is_base_model,
    )

    if request.GET.get("format") == "htmx-search-results":
        results = [f'<li data-value="{m.id}">{m}</li>' for m in models]
        if not results:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse("\n".join(results))

    return render(
        request,
        "assets/models/list.html",
        {
            "models": models,
            "q": q,
            "asset_class": asset_class,
            **_form_choices(),
        },
    )


def _get_or_404(model_id: int):
    model = load_model_detail(model_id)
    if model is None:
        raise Http404
    return model


@require_http_methods(["GET"])
def model_detail(request: HttpRequest, model_id: int) -> HttpResponse:
    return render(request, "assets/models/detail.html", {"model": _get_or_404(model_id)})


@require_http_methods(["GET", "POST"])
def model_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = AssetModelCreateAdaptor.from_post(request.POST)
        if data.get("asset_class_id") is None:
            messages.error(request, "An asset class is required.")
            return render(
                request,
                "assets/models/form.html",
                {"mode": "create", "model": data, **_form_choices()},
            )
        try:
            model = AssetModelFactory.create(data=data, actor=request.user)
        except AssetModelValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/models/form.html",
                {"mode": "create", "model": data, **_form_choices()},
            )
        messages.success(request, f"Model '{model}' created.")
        return redirect(reverse("model_detail", kwargs={"model_id": model.id}))
    return render(
        request,
        "assets/models/form.html",
        {"mode": "create", "model": None, **_form_choices()},
    )


@require_http_methods(["GET", "POST"])
def model_edit(request: HttpRequest, model_id: int) -> HttpResponse:
    model = _get_or_404(model_id)
    if request.method == "POST":
        data = AssetModelEditAdaptor.from_post(request.POST)
        context = AssetModelContext(model_id, actor=request.user)
        context.update(data=data)
        context.set_capabilities(capability_ids=data["assigned_capability_ids"])
        messages.success(request, f"Model '{context.model}' updated.")
        return redirect(reverse("model_detail", kwargs={"model_id": model_id}))

    assigned_capability_ids = set(
        model.capability_links.values_list("capability_definition_id", flat=True)
    )
    all_definitions = CapabilityDefinition.objects.order_by("name")
    assigned_capabilities = [d for d in all_definitions if d.id in assigned_capability_ids]
    available_capabilities = [
        d for d in all_definitions if d.id not in assigned_capability_ids
    ]
    selected_manufacturer_ids = set(model.manufacturers.values_list("id", flat=True))

    return render(
        request,
        "assets/models/form.html",
        {
            "mode": "edit",
            "model": model,
            "selected_manufacturer_ids": selected_manufacturer_ids,
            "assigned_capabilities": assigned_capabilities,
            "available_capabilities": available_capabilities,
            **_form_choices(),
        },
    )
