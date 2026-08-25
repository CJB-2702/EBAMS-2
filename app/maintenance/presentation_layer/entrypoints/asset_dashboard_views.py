"""The fleet-health assets dashboard: maintenance overview from an asset
perspective, one large card per asset, infinite-scroll (events app's
ev_list_large / event_cards_page pattern)."""

from __future__ import annotations

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.assets.models import AssetClass, AssetModel, Manufacturer
from app.maintenance.control_layer.domain_structs.asset_maintenance_dashboard_struct import (
    AssetMaintenanceDashboardBuilder,
)
from app.maintenance.presentation_layer.search.asset_dashboard_search import (
    AssetDashboardSearch,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
)

CARDS_PER_PAGE = 12


def _form_choices() -> dict:
    return {
        "classes": AssetClass.objects.order_by("name"),
        "models": AssetModel.objects.order_by("model_name", "version_rank", "version"),
        "manufacturers": Manufacturer.objects.order_by("name"),
    }


@require_http_methods(["GET"])
def asset_dashboard(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)

    filters = {
        key: request.GET.get(key, "").strip()
        for key in (
            "q", "asset_class", "model", "manufacturer",
            "planned_date_from", "planned_date_to",
            "started_date_from", "started_date_to",
        )
    }
    has_blockers = request.GET.get("has_blockers") == "1"
    has_limitations = request.GET.get("has_limitations") == "1"

    assets = AssetDashboardSearch.index_list(
        domain_ids=domain_ids,
        q=filters["q"],
        asset_class=filters["asset_class"],
        model=filters["model"],
        manufacturer=filters["manufacturer"],
        planned_date_from=filters["planned_date_from"] or None,
        planned_date_to=filters["planned_date_to"] or None,
        started_date_from=filters["started_date_from"] or None,
        started_date_to=filters["started_date_to"] or None,
        has_blockers=has_blockers,
        has_limitations=has_limitations,
    )

    # Querystring carrying just the active filters (no page / format) so the
    # infinite-scroll sentinel can preserve filter state across pages.
    filter_params = {k: v for k, v in filters.items() if v}
    if has_blockers:
        filter_params["has_blockers"] = "1"
    if has_limitations:
        filter_params["has_limitations"] = "1"
    base_query = urlencode(filter_params)

    page_obj = Paginator(assets, CARDS_PER_PAGE).get_page(request.GET.get("page"))
    cards = AssetMaintenanceDashboardBuilder.build_for_page(page_obj.object_list)

    fmt = request.GET.get("format", "").strip()
    current_format = "condensed" if fmt == "condensed" else "comfortable"

    card_ctx = {
        "cards": cards,
        "page_obj": page_obj,
        "base_query": base_query,
        "current_format": current_format,
    }
    if fmt == "htmx-asset-cards":
        return render(
            request, "maintenance/fragments/asset_dashboard_cards_page.html", card_ctx
        )
    if fmt == "htmx-asset-condensed":
        return render(
            request, "maintenance/fragments/asset_dashboard_condensed_page.html", card_ctx
        )

    return render(
        request,
        "maintenance/asset_dashboard.html",
        {
            **filters,
            "has_blockers": has_blockers,
            "has_limitations": has_limitations,
            "metrics": AssetDashboardSearch.key_metrics(domain_ids=domain_ids),
            **_form_choices(),
            **card_ctx,
        },
    )
