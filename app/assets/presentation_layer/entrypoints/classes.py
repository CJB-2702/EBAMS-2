"""Asset Class list / detail / create / edit — wired to the control layer.

Reads go through ``presentation_layer/search``; writes go through the
``AssetClassFactory`` (create) and ``AssetClassContext`` (edit metadata, domains,
and declared capability set).
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.control_layer.adapters.asset_class_adaptor import (
    AssetClassCreateAdaptor,
    AssetClassEditAdaptor,
)
from app.assets.control_layer.asset_class_context import (
    AssetClassContext,
    AssetClassValidationError as AssetClassEditValidationError,
)
from app.assets.control_layer.factories.asset_class_factory import (
    AssetClassFactory,
    AssetClassValidationError,
)
from app.assets.models import CapabilityDefinition
from app.assets.presentation_layer.search.asset_class_search import (
    list_categories,
    load_asset_class_detail,
    search_asset_classes,
)


def _domains():
    return Domain.objects.order_by("name")


@require_http_methods(["GET"])
def class_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    domain = request.GET.get("domain", "").strip()
    classes = search_asset_classes(q=q, category=category, domain=domain)

    if request.GET.get("format") == "htmx-search-results":
        results = [f'<li data-value="{c.id}">{c.name}</li>' for c in classes]
        if not results:
            return HttpResponse('<li class="is-disabled">No matches.</li>')
        return HttpResponse("\n".join(results))

    return render(
        request,
        "assets/classes/list.html",
        {
            "classes": classes,
            "q": q,
            "category": category,
            "domain": domain,
            "domains": _domains(),
            "categories": list_categories(),
        },
    )


def _get_or_404(class_id: int):
    klass = load_asset_class_detail(class_id)
    if klass is None:
        raise Http404
    return klass


@require_http_methods(["GET"])
def class_detail(request: HttpRequest, class_id: int) -> HttpResponse:
    return render(request, "assets/classes/detail.html", {"klass": _get_or_404(class_id)})


@require_http_methods(["GET", "POST"])
def class_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        data = AssetClassCreateAdaptor.from_post(request.POST)
        try:
            asset_class = AssetClassFactory.create(data=data, actor=request.user)
        except AssetClassValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
            return render(
                request,
                "assets/classes/form.html",
                {"mode": "create", "klass": data, "domains": _domains()},
            )
        messages.success(request, f"Asset class '{asset_class.name}' created.")
        return redirect(reverse("class_detail", kwargs={"class_id": asset_class.id}))
    return render(
        request,
        "assets/classes/form.html",
        {"mode": "create", "klass": None, "domains": _domains()},
    )


@require_http_methods(["GET", "POST"])
def class_edit(request: HttpRequest, class_id: int) -> HttpResponse:
    klass = _get_or_404(class_id)
    if request.method == "POST":
        data = AssetClassEditAdaptor.from_post(request.POST)
        try:
            context = AssetClassContext(class_id, actor=request.user)
            context.update(data=data)
            context.set_capabilities(capability_ids=data["assigned_capability_ids"])
        except AssetClassEditValidationError as exc:
            for error in exc.errors:
                messages.error(request, error)
        else:
            messages.success(request, f"Asset class '{klass.name}' updated.")
            return redirect(reverse("class_detail", kwargs={"class_id": class_id}))

    assigned_capability_ids = set(
        klass.capability_links.values_list("capability_definition_id", flat=True)
    )
    all_definitions = CapabilityDefinition.objects.order_by("name")
    assigned_capabilities = [d for d in all_definitions if d.id in assigned_capability_ids]
    available_capabilities = [
        d for d in all_definitions if d.id not in assigned_capability_ids
    ]
    selected_domain_ids = set(klass.domains.values_list("id", flat=True))

    return render(
        request,
        "assets/classes/form.html",
        {
            "mode": "edit",
            "klass": klass,
            "domains": _domains(),
            "selected_domain_ids": selected_domain_ids,
            "assigned_capabilities": assigned_capabilities,
            "available_capabilities": available_capabilities,
        },
    )
