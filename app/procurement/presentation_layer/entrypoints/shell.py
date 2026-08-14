"""The application shell: the `/procurement` hub and the shared "not built
yet" placeholder for routes declared by Phase 0 but owned by a later wave.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.procurement.models import (
    DemandState,
    Package,
    PurchaseOrder,
    PurchaseOrderApprovalState,
    PurchaseOrderStatus,
)
from app.procurement.presentation_layer.search.unpriced_part_search import (
    UnpricedPartSearch,
)
from app.procurement.presentation_layer.tools.procurement_access import (
    accessible_domain_ids,
    can_buy,
)


@require_http_methods(["GET"])
def not_built_yet(request: HttpRequest) -> HttpResponse:
    """Shared placeholder for any Phase 0-declared route not yet owned by a
    landed wave. Route names are pre-declared here so waves 1-3 could be built
    in parallel against a stable URL contract (Phase 0 §6)."""
    return render(
        request,
        "procurement/_not_built_yet.html",
        {"feature": request.resolver_match.url_name.replace("_", " ").title()},
        status=501,
    )


@require_http_methods(["GET"])
def procurement_hub(request: HttpRequest) -> HttpResponse:
    """Index/portal hub shell (page_structure.md) — entry-card grid plus a
    one-query, domain-scoped stat bar (Phase 0 §7)."""
    domain_ids = accessible_domain_ids(request)

    demand_stats = PartDemandAgg.for_domains(domain_ids)
    po_stats = _po_stats(domain_ids)
    package_stats = _package_stats(domain_ids)
    can_buy_prices = can_buy(request)

    return render(
        request,
        "procurement/hub.html",
        {
            "open_demands": demand_stats["open"],
            "demands_pending_approval": demand_stats["pending_approval"],
            "pos_pending_approval": po_stats["pending_approval"],
            "draft_pos": po_stats["draft"],
            "packages_in_transit": package_stats["in_transit"],
            "drift_flagged_packages": package_stats["drift_flagged"],
            "can_buy_prices": can_buy_prices,
            # D87: viewer-relative — see the unpriced page's own caveat.
            "unpriced_parts_count": (
                UnpricedPartSearch.count(domain_ids=domain_ids) if can_buy_prices else 0
            ),
        },
    )


#: "Open" reads as not-yet-terminal — still moving through the pipeline.
_OPEN_DEMAND_STATES = (DemandState.PROJECTED, DemandState.REQUIRED, DemandState.APPROVED)


class PartDemandAgg:
    """One aggregate query for the hub's demand-side stats."""

    @staticmethod
    def for_domains(domain_ids: list[int]) -> dict[str, int]:
        from app.procurement.models import PartDemand

        agg = PartDemand.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True
        ).aggregate(
            open=Count("pk", filter=Q(demand_state__in=_OPEN_DEMAND_STATES)),
            # Required = raised and awaiting a demand_state decision.
            pending_approval=Count("pk", filter=Q(demand_state=DemandState.REQUIRED)),
        )
        return agg


def _po_stats(domain_ids: list[int]) -> dict[str, int]:
    agg = PurchaseOrder.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).aggregate(
        pending_approval=Count(
            "pk",
            filter=Q(approval_state=PurchaseOrderApprovalState.PENDING_APPROVAL),
        ),
        draft=Count("pk", filter=Q(status=PurchaseOrderStatus.DRAFT)),
    )
    return agg


def _package_stats(domain_ids: list[int]) -> dict[str, int]:
    in_transit_statuses = ("awaiting_shipment", "shipped", "delivered_to_depot")
    agg = Package.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).aggregate(
        in_transit=Count("pk", filter=Q(status__in=in_transit_statuses)),
        drift_flagged=Count("pk", filter=Q(mixed_po_assignments=True)),
    )
    return agg
