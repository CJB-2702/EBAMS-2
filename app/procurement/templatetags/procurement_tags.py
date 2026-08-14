"""Template tags shared across the demand loop's list/edit/detail pages.

Centralizes the "Backordered and Partially Issued are everyday states, not
alarming ones" rule (D44, part_demand_workflows.md §2.1) so every page that
renders an axis badge gets the same, deliberately calm, colour choice rather
than each template re-deciding it.
"""

from __future__ import annotations

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.control_layer.narrators.part_price_narrator import (
    PartPriceNarrator,
)
from app.procurement.presentation_layer.tools.procurement_access import (
    is_in_domain,
)
from app.procurement.models import (
    DemandPriority,
    DemandState,
    IssuanceState,
    PackageStatus,
    PriceConfidence,
    PurchasingState,
    ShipmentState,
)

register = template.Library()

#: Package movement reads calm all the way along — a box in transit is the
#: normal case, not a problem. Only Lost earns the danger treatment, and only
#: Accepted earns success: it is the one status that means "done, and intact".
_PACKAGE_STATUS_CLASS = {
    PackageStatus.AWAITING_SHIPMENT: "is-light",
    PackageStatus.BACKORDERED: "is-warning is-light",
    PackageStatus.SHIPPED: "is-info is-light",
    PackageStatus.DELIVERED_TO_DEPOT: "is-info is-light",
    PackageStatus.DELIVERED_TO_LOCAL: "is-link is-light",
    PackageStatus.ACCEPTED: "is-success is-light",
    PackageStatus.LOST: "is-danger is-light",
    PackageStatus.CANCELLED: "is-danger is-light",
}


@register.simple_tag
def package_status_tag(status: str):
    css = _PACKAGE_STATUS_CLASS.get(status, "is-light")
    label = dict(PackageStatus.choices).get(status, status or "—")
    return format_html('<span class="tag is-small {}">{}</span>', css, label)


@register.simple_tag
def accepted_quantity_cell(quantity_accepted, quantity):
    """`null` and `0` are DIFFERENT FACTS and this is the one place that is
    decided.

    Uninspected means nobody has looked. Zero means somebody looked and
    rejected everything. Rendering both as "0" — or worse, defaulting the input
    to 0 — turns a missing inspection into a recorded write-off.
    """
    if quantity_accepted is None:
        return mark_safe(
            '<span class="tag is-small is-light has-text-grey">Not inspected</span>'
        )
    if quantity_accepted == 0:
        return mark_safe(
            '<span class="tag is-small is-danger is-light">0 accepted — all rejected</span>'
        )
    css = "is-success is-light" if quantity_accepted >= quantity else "is-warning is-light"
    return format_html(
        '<span class="tag is-small {}">{} of {}</span>', css, quantity_accepted, quantity
    )

_PRIORITY_CLASS = {
    DemandPriority.CRITICAL: "is-danger is-light",
    DemandPriority.HIGH: "is-warning is-light",
    DemandPriority.MEDIUM: "is-light",
    DemandPriority.LOW: "is-light",
}

#: Only genuinely negative/terminal-bad stages get the danger treatment.
_DANGER_STAGES = {
    DemandState.REJECTED,
    DemandState.CANCELLED,
    PurchasingState.DENIED,
    PurchasingState.CANCELLED,
    ShipmentState.LOST,
}

#: Positive/terminal-good stages.
_SUCCESS_STAGES = {
    DemandState.COMPLETED,
    DemandState.APPROVED,
    PurchasingState.APPROVED,
    PurchasingState.PURCHASED,
    ShipmentState.DELIVERED_TO_LOCAL,
    ShipmentState.DELIVERED_TO_DEPOT,
    IssuanceState.ISSUED,
}


@register.simple_tag
def demand_priority_tag(priority: str):
    css = _PRIORITY_CLASS.get(priority, "is-light")
    label = dict(DemandPriority.choices).get(priority, priority or "—")
    return format_html('<span class="tag is-small {}">{}</span>', css, label)


@register.simple_tag(takes_context=True)
def demand_in_domain(context, domain_id):
    """Phase 0 §5's cross-domain rule: a record outside the user's domain
    access renders as plain text, never a link. Templates gate an <a> on this
    rather than hiding the record entirely."""
    request = context.get("request")
    if request is None:
        return False
    return is_in_domain(request, domain_id)


@register.simple_tag
def demand_axis_tag(dimension: str, stage: str):
    label = PartDemandNarrator.stage_label(dimension=dimension, stage=stage)
    if stage in _DANGER_STAGES:
        css = "is-danger is-light"
    elif stage in _SUCCESS_STAGES:
        css = "is-success is-light"
    else:
        # Everything else — including Backordered and Partially Issued — reads
        # as a normal, everyday state (D44), never alarming.
        css = "is-light"
    return format_html('<span class="tag is-small {}">{}</span>', css, label)


@register.simple_tag
def price_staleness(observed_at):
    """"3 days ago", "14 months ago" — the narrator owns every price phrase
    (front_end_build_plan.md §1 rule 7); no template does its own date maths."""
    return PartPriceNarrator.staleness(observed_at)


_CONFIDENCE_CLASS = {
    PriceConfidence.QUOTED: "is-success is-light",
    PriceConfidence.P10: "is-light",
    PriceConfidence.P50: "is-warning is-light",
    PriceConfidence.P100: "is-warning is-light",
    PriceConfidence.UNKNOWN: "is-light has-text-grey",
}


@register.simple_tag
def price_confidence_tag(confidence: str):
    css = _CONFIDENCE_CLASS.get(confidence, "is-light")
    label = dict(PriceConfidence.choices).get(confidence, confidence or "—")
    return format_html('<span class="tag is-small {}">{}</span>', css, label)


@register.filter
def dict_get(mapping, key):
    """`{{ price_facts|dict_get:part_id }}` — Django templates cannot
    subscript a dict by a variable key without a filter."""
    if mapping is None:
        return None
    return mapping.get(key)
