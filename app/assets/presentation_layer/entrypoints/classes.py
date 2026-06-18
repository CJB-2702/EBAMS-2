"""Asset Class list / detail / create / edit (mock)."""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def class_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip().lower()
    classes = mock.get_classes()
    if q:
        classes = [c for c in classes if q in c.name.lower() or (c.category and q in c.category.lower())]
    categories = sorted(list(set(c["category"] for c in mock.ASSET_CLASSES if c.get("category"))))
    return render(request, "assets/classes/list.html", {
        "classes": classes, "q": q, "domains": mock.DOMAINS, "categories": categories
    })


def _get_or_404(class_id):
    c = mock.get_class(class_id)
    if c is None:
        raise Http404
    return c


@require_http_methods(["GET"])
def class_detail(request: HttpRequest, class_id: int) -> HttpResponse:
    return render(request, "assets/classes/detail.html", {"klass": _get_or_404(class_id)})


@require_http_methods(["GET", "POST"])
def class_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        messages.success(request, "Asset class created (mock — not persisted).")
        return redirect(reverse("class_index"))
    return render(request, "assets/classes/form.html", {"mode": "create", "klass": None, "domains": mock.DOMAINS})


@require_http_methods(["GET", "POST"])
def class_edit(request: HttpRequest, class_id: int) -> HttpResponse:
    klass = _get_or_404(class_id)
    if request.method == "POST":
        messages.success(request, f"Asset class '{klass.name}' updated (mock — not persisted).")
        return redirect(reverse("class_detail", kwargs={"class_id": class_id}))
        
    assigned_capability_ids = {r["capability_definition"] for r in mock.ASSET_CLASS_CAPABILITIES if r["asset_class"] == class_id}
    all_definitions = mock.get_capability_definitions()
    
    assigned_capabilities = [d for d in all_definitions if d.id in assigned_capability_ids]
    available_capabilities = [d for d in all_definitions if d.id not in assigned_capability_ids]
    
    return render(request, "assets/classes/form.html", {
        "mode": "edit", "klass": klass, "domains": mock.DOMAINS,
        "assigned_capabilities": assigned_capabilities,
        "available_capabilities": available_capabilities,
    })
