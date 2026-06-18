"""Asset Model list / detail / create / edit (mock)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def model_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    klass = request.GET.get("asset_class", "").strip()
    models = mock.get_models()
    if q:
        models = [m for m in models if q in m.display_name.lower()]
    if klass:
        models = [m for m in models if m.asset_class and str(m.asset_class.id) == klass]
        
    if request.GET.get("format") == "htmx-search-results":
        results = [
            f'<li data-value="{m.id}">{m.display_name}</li>'
            for m in models
        ]
        if not results:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse("\n".join(results))

    return render(request, "assets/models/list.html", {
        "models": models, "q": q, "asset_class": klass, 
        "classes": mock.ASSET_CLASSES, "manufacturers": mock.MANUFACTURERS,
        "domains": mock.DOMAINS,
    })


def _get_or_404(model_id):
    m = mock.get_model(model_id)
    if m is None:
        raise Http404
    return m


@require_http_methods(["GET"])
def model_detail(request: HttpRequest, model_id: int) -> HttpResponse:
    return render(request, "assets/models/detail.html", {"model": _get_or_404(model_id)})


@require_http_methods(["GET", "POST"])
def model_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Model created (mock — not persisted).")
        return redirect(reverse("model_index"))
    return render(request, "assets/models/form.html", {
        "mode": "create", "model": None,
        "classes": mock.ASSET_CLASSES, "manufacturers": mock.MANUFACTURERS, "domains": mock.DOMAINS,
    })


@require_http_methods(["GET", "POST"])
def model_edit(request: HttpRequest, model_id: int) -> HttpResponse:
    model = _get_or_404(model_id)
    if request.method == "POST":
        messages.success(request, f"Model '{model.display_name}' updated (mock — not persisted).")
        return redirect(reverse("model_detail", kwargs={"model_id": model_id}))
        
    assigned_capability_ids = {r["capability_definition"] for r in mock.MODEL_CAPABILITIES if r["model"] == model_id}
    all_definitions = mock.get_capability_definitions()
    
    assigned_capabilities = [d for d in all_definitions if d.id in assigned_capability_ids]
    available_capabilities = [d for d in all_definitions if d.id not in assigned_capability_ids]
    
    return render(request, "assets/models/form.html", {
        "mode": "edit", "model": model,
        "classes": mock.ASSET_CLASSES, "manufacturers": mock.MANUFACTURERS, "domains": mock.DOMAINS,
        "assigned_capabilities": assigned_capabilities,
        "available_capabilities": available_capabilities,
    })
