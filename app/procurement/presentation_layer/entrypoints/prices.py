"""The price-observation wave: hub, the bulk paste grid, the unpriced-parts
backstop, and one part's full price history (+ its chip/picker/card format
variants). price_observation_mini_kit/front_end_build_plan.md is the spec.

Same four rules as purchase_orders.py, plus the kit's own:
5. Domain filtering is a security boundary — `domain_ids` is read once per
   view and threaded downward; no search module or template touches
   `request` or the session for it.
6. `price_establish` changes what a control *means*, never where it is — the
   grid looks identical for both authority levels; only the "Record as
   verified" checkbox appears or does not.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.parts.control_layer.adapters.form_parsing import parse_int
from app.procurement.control_layer.adapters.part_price_grid_adaptor import (
    PartPriceGridAdaptor,
)
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.part_price_observation_bulk_factory import (
    PartPriceObservationBulkFactory,
)
from app.procurement.control_layer.factories.part_price_observation_factory import (
    PartPriceObservationFactory,
)
from app.procurement.control_layer.policies.part_price_policy import PartPricePolicy
from app.procurement.models import (
    PartPriceObservation,
    PriceConfidence,
    PriceSourceType,
    Vendor,
)
from app.procurement.presentation_layer.search.part_price_history_search import (
    PartPriceHistorySearch,
)
from app.procurement.presentation_layer.search.part_price_observation_search import (
    PartPriceObservationSearch,
)
from app.procurement.presentation_layer.search.part_visibility import visible_parts_qs
from app.procurement.presentation_layer.search.unpriced_part_search import (
    UnpricedPartSearch,
)
from app.procurement.presentation_layer.tools import price_grid_draft as grid_draft
from app.procurement.presentation_layer.tools import recent_part_creations
from app.procurement.presentation_layer.tools.procurement_access import (
    accessible_domain_ids,
    can_establish_price,
    require_buy_prices,
)

TEMPLATE_DIR = "procurement/prices"
PAGE_SIZE = 50


# ====================================================================== #
# price_hub — /procurement/prices/
# ====================================================================== #


@require_http_methods(["GET"])
def price_hub(request: HttpRequest) -> HttpResponse:
    require_buy_prices(request)
    domain_ids = accessible_domain_ids(request)
    can_establish = can_establish_price(request)

    filters = {
        "q": (request.GET.get("q") or "").strip(),
        "vendor_id": parse_int(request.GET.get("vendor_id")),
        "domain_id": parse_int(request.GET.get("domain_id")),
        "source_type": (request.GET.get("source_type") or "").strip(),
        "confidence": (request.GET.get("confidence") or "").strip(),
        "is_verified": (request.GET.get("is_verified") or "").strip(),
        "observed_from": parse_date(request.GET.get("observed_from") or ""),
        "observed_to": parse_date(request.GET.get("observed_to") or ""),
    }
    results = PartPriceObservationSearch.results(domain_ids=domain_ids, **filters)
    paginator = Paginator(results, PAGE_SIZE)
    page = paginator.get_page(parse_int(request.GET.get("page")) or 1)

    carry_qs = request.GET.copy()
    carry_qs.pop("page", None)
    carry_qs.pop("format", None)

    context = {
        "page": page,
        "total": paginator.count,
        "filters": filters,
        "carry_qs": carry_qs.urlencode(),
        "can_establish": can_establish,
        "unpriced_count": UnpricedPartSearch.count(domain_ids=domain_ids),
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
        "source_types": PriceSourceType.choices,
        "confidences": PriceConfidence.choices,
    }
    if can_establish:
        context["unverified_count"] = _unverified_disagreement_count(domain_ids)
    if request.GET.get("format") == "htmx-results":
        return render(request, f"{TEMPLATE_DIR}/_hub_results.html", context)
    return render(request, f"{TEMPLATE_DIR}/hub.html", context)


def _unverified_disagreement_count(domain_ids: list[int]) -> int:
    """D89's review workload: unverified observations whose cost disagrees
    with an established price on the same (part, vendor, domain). No
    approval inbox — this is a filter over rows that already exist."""
    from django.db.models import Exists, OuterRef

    disagreeing_verified = PartPriceObservation.objects.filter(
        part_id=OuterRef("part_id"),
        vendor_id=OuterRef("vendor_id"),
        domain_id=OuterRef("domain_id"),
        is_verified=True,
    ).exclude(unit_cost=OuterRef("unit_cost"))
    return (
        PartPriceObservation.objects.filter(domain_id__in=domain_ids, is_verified=False)
        .filter(Exists(disagreeing_verified))
        .values("part_id", "vendor_id", "domain_id")
        .distinct()
        .count()
    )


# ====================================================================== #
# price_bulk_grid — /procurement/prices/bulk/
# ====================================================================== #


@require_http_methods(["GET", "POST"])
def price_bulk_grid(request: HttpRequest) -> HttpResponse:
    require_buy_prices(request)
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _grid_post(request, domain_ids=domain_ids)

    if request.GET.get("format") == "htmx-part-results":
        return _part_search_fragment(request, domain_ids=domain_ids)

    return _grid_render(request, domain_ids=domain_ids)


def _part_search_fragment(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    from django.db.models import Q

    q = request.GET.get("q", "").strip()
    parts = visible_parts_qs(domain_ids=domain_ids)
    if q:
        parts = parts.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    parts = parts.order_by("part_number")[:25]

    rows = [
        f'<li data-value="{p.pk}" class="is-family-monospace">{p.part_number}'
        f'<span class="has-text-grey is-size-7"> — {p.name}</span></li>'
        for p in parts
    ]
    if not rows:
        rows = ['<li class="is-disabled">No matches.</li>']
    return HttpResponse("\n".join(rows))


def _grid_post(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    """POST -> redirect -> GET throughout, mirroring purchase_orders.py's
    wizard: every mutation writes to the session draft and redirects back to
    the same canonical URL. HTMX forms carry hx-target/hx-select of
    #procurement-main-content (the create.html precedent) rather than a
    separate fragment format — one fewer response shape to keep in sync,
    and the plain-POST fallback is identical by construction."""
    action = request.POST.get("action", "")

    if action == "dismiss_banner":
        recent_part_creations.dismiss(request)
        return redirect(reverse("price_bulk_grid"))

    if action == "load_banner":
        part_ids = recent_part_creations.visible_banner_parts(request, actor=request.user)
        draft = grid_draft.load(request.session)
        grid_draft.add_rows(draft, part_ids=part_ids)
        grid_draft.save(request.session, draft)
        return redirect(reverse("price_bulk_grid"))

    if action == "add_row":
        part_id = parse_int(request.POST.get("part_id"))
        draft = grid_draft.load(request.session)
        if part_id:
            grid_draft.add_rows(draft, part_ids=[part_id])
        grid_draft.save(request.session, draft)
        return redirect(reverse("price_bulk_grid"))

    if action == "add_rows_bulk":
        part_ids = [pid for pid in (parse_int(v) for v in request.POST.getlist("part_ids")) if pid]
        draft = grid_draft.load(request.session)
        grid_draft.add_rows(draft, part_ids=part_ids)
        grid_draft.save(request.session, draft)
        if part_ids:
            messages.success(request, f"{len(part_ids)} part(s) added to the price grid.")
        return redirect(reverse("price_bulk_grid"))

    if action == "sync":
        draft = grid_draft.load(request.session)
        _sync_draft_from_post(draft, request.POST)
        remove_part_id = parse_int(request.POST.get("remove_part_id"))
        if remove_part_id:
            grid_draft.remove_row(draft, part_id=remove_part_id)
        grid_draft.save(request.session, draft)
        return redirect(reverse("price_bulk_grid"))

    if action == "save_all":
        return _grid_save(request, domain_ids=domain_ids)

    messages.error(request, "Unrecognised grid action.")
    return redirect(reverse("price_bulk_grid"))


def _sync_draft_from_post(draft: dict, post) -> None:
    """Full-form sync used by the grid's own header/row-value changes and
    the remove-row action — everything that happens *inside* the outer
    grid <form>, which always carries the whole current state."""
    grid_draft.set_header(
        draft,
        vendor_id=parse_int(post.get("vendor_id")),
        domain_id=parse_int(post.get("domain_id")),
        observed_at=(post.get("observed_at") or "").strip() or None,
        source_type=(post.get("source_type") or "").strip(),
        confidence=(post.get("confidence") or "").strip(),
        notes=(post.get("notes") or "").strip(),
        record_as_verified=post.get("record_as_verified") in ("on", "true", "1"),
    )
    count = parse_int(post.get("row_count")) or 0
    for i in range(count):
        prefix = f"rows-{i}-"
        part_id = parse_int(post.get(f"{prefix}part_id"))
        if part_id is None:
            continue
        grid_draft.set_row_values(
            draft,
            part_id=part_id,
            quantity=(post.get(f"{prefix}quantity") or "").strip(),
            unit_cost=(post.get(f"{prefix}unit_cost") or "").strip(),
        )


def _grid_save(request: HttpRequest, *, domain_ids: list[int]) -> HttpResponse:
    draft = grid_draft.load(request.session)
    _sync_draft_from_post(draft, request.POST)
    grid_draft.save(request.session, draft)

    parsed = PartPriceGridAdaptor.from_post(request.POST)
    if parsed.errors:
        return _grid_render(request, domain_ids=domain_ids, errors=parsed.errors)
    if not parsed.rows:
        return _grid_render(
            request,
            domain_ids=domain_ids,
            errors=["No priced rows to save — every row was left blank."],
        )

    part_ids = [row.part_id for row in parsed.rows]
    visible_part_ids = set(
        visible_parts_qs(domain_ids=domain_ids)
        .filter(pk__in=part_ids)
        .values_list("pk", flat=True)
    )

    try:
        result = PartPriceObservationBulkFactory.create_many(
            rows=parsed.rows,
            actor=request.user,
            visible_part_ids=visible_part_ids,
            visible_domain_ids=domain_ids,
            actor_can_establish=can_establish_price(request),
            dropped_part_ids=parsed.dropped_part_ids,
        )
    except ProcurementValidationError as exc:
        return _grid_render(request, domain_ids=domain_ids, errors=exc.errors)

    recent_part_creations.consume(request, part_ids=part_ids)
    grid_draft.clear(request.session)
    return _grid_render(request, domain_ids=domain_ids, result=result)


def _hydrate_rows(draft: dict, *, domain_ids: list[int]) -> list[dict]:
    part_ids = [row["part_id"] for row in draft["rows"]]
    parts_by_id = {
        p.pk: p for p in visible_parts_qs(domain_ids=domain_ids).filter(pk__in=part_ids)
    }
    hydrated = []
    for row in draft["rows"]:
        part = parts_by_id.get(row["part_id"])
        hydrated.append(
            {
                "part_id": row["part_id"],
                "part_number": part.part_number if part else f"#{row['part_id']} (not visible)",
                "part_name": part.name if part else "",
                "quantity": row.get("quantity") or "",
                "unit_cost": row.get("unit_cost") or "",
            }
        )
    return hydrated


def _grid_context(request: HttpRequest, *, domain_ids: list[int]) -> dict:
    draft = grid_draft.load(request.session)
    rows = _hydrate_rows(draft, domain_ids=domain_ids)
    selected_vendor = (
        Vendor.objects.filter(pk=draft["vendor_id"]).first() if draft["vendor_id"] else None
    )
    recent_ids = recent_part_creations.visible_banner_parts(request, actor=request.user)
    from app.parts.models import Part

    return {
        "draft": draft,
        "rows": rows,
        "row_count": len(rows),
        "priced_count": sum(1 for r in rows if r["unit_cost"]),
        "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "source_types": PriceSourceType.choices,
        "confidences": PriceConfidence.choices,
        "selected_vendor": selected_vendor,
        "recent_banner": {
            "parts": (
                list(Part.objects.filter(pk__in=recent_ids).order_by("part_number"))
                if recent_ids
                else []
            ),
            "overflowed": recent_part_creations.read_recent_overflowed(request),
        },
        "can_establish": can_establish_price(request),
    }


def _grid_render(
    request: HttpRequest, *, domain_ids: list[int], errors=None, result=None
) -> HttpResponse:
    context = _grid_context(request, domain_ids=domain_ids)
    context["errors"] = errors or []
    context["result"] = result
    return render(request, f"{TEMPLATE_DIR}/bulk.html", context)


# ====================================================================== #
# unpriced_parts — /procurement/prices/unpriced/  (D86 backstop)
# ====================================================================== #


@require_http_methods(["GET"])
def unpriced_parts(request: HttpRequest) -> HttpResponse:
    require_buy_prices(request)
    domain_ids = accessible_domain_ids(request)

    filters = {
        "domain_id": parse_int(request.GET.get("domain_id")),
        "created_from": parse_date(request.GET.get("created_from") or ""),
        "part_type": (request.GET.get("part_type") or "").strip(),
        "q": (request.GET.get("q") or "").strip(),
    }
    results = UnpricedPartSearch.results(domain_ids=domain_ids, **filters)
    paginator = Paginator(results, PAGE_SIZE)
    page = paginator.get_page(parse_int(request.GET.get("page")) or 1)

    part_types = list(
        visible_parts_qs(domain_ids=domain_ids)
        .exclude(part_type="")
        .order_by("part_type")
        .values_list("part_type", flat=True)
        .distinct()
    )

    context = {
        "page": page,
        "filters": filters,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "part_types": part_types,
        "total": paginator.count,
    }
    if request.GET.get("format") == "htmx-results":
        return render(request, f"{TEMPLATE_DIR}/_unpriced_results.html", context)
    return render(request, f"{TEMPLATE_DIR}/unpriced.html", context)


# ====================================================================== #
# part_price_history — /procurement/prices/parts/<part_id>/
# ====================================================================== #


@require_http_methods(["GET", "POST"])
def part_price_history(request: HttpRequest, part_id: int) -> HttpResponse:
    require_buy_prices(request)
    domain_ids = accessible_domain_ids(request)
    part = get_object_or_404(visible_parts_qs(domain_ids=domain_ids), pk=part_id)

    if request.method == "POST":
        return _verify_observation(request, part=part, domain_ids=domain_ids)

    fmt = request.GET.get("format")
    if fmt == "htmx-chip":
        return _chip_fragment(request, part=part, domain_ids=domain_ids)
    if fmt == "htmx-picker":
        return _picker_fragment(request, part=part, domain_ids=domain_ids)
    if fmt == "htmx-card":
        return _card_fragment(request, part=part, domain_ids=domain_ids)

    return _history_render(request, part=part, domain_ids=domain_ids)


def _chip_fragment(request: HttpRequest, *, part, domain_ids: list[int]) -> HttpResponse:
    vendor_id = parse_int(request.GET.get("vendor_id"))
    if not vendor_id:
        return HttpResponse("")
    facts = PartPricePolicy.facts_for(part_id=part.id, vendor_id=vendor_id, domain_ids=domain_ids)
    vendor = Vendor.objects.filter(pk=vendor_id).first()
    return render(
        request,
        f"{TEMPLATE_DIR}/_price_chip.html",
        {
            "facts": facts,
            "part_id": part.id,
            "vendor": vendor,
            "handle": request.GET.get("handle", ""),
        },
    )


def _picker_fragment(request: HttpRequest, *, part, domain_ids: list[int]) -> HttpResponse:
    total = PartPriceHistorySearch.for_part(part_id=part.id, domain_ids=domain_ids).count()
    observations = list(
        PartPriceHistorySearch.for_part(part_id=part.id, domain_ids=domain_ids, limit=50)
    )
    return render(
        request,
        f"{TEMPLATE_DIR}/_price_picker.html",
        {
            "part": part,
            "observations": observations,
            "total": total,
            "truncated": total > len(observations),
            "target_input_id": request.GET.get("target_input_id", ""),
        },
    )


def _card_fragment(request: HttpRequest, *, part, domain_ids: list[int]) -> HttpResponse:
    observations = list(
        PartPriceHistorySearch.for_part(part_id=part.id, domain_ids=domain_ids, limit=5)
    )
    return render(
        request,
        f"{TEMPLATE_DIR}/_pricing_card.html",
        {"part": part, "observations": observations},
    )


def _history_render(request: HttpRequest, *, part, domain_ids: list[int]) -> HttpResponse:
    vendor_id = parse_int(request.GET.get("vendor_id"))
    domain_id = parse_int(request.GET.get("domain_id"))
    observations = list(
        PartPriceHistorySearch.for_part(
            part_id=part.id, domain_ids=domain_ids, vendor_id=vendor_id, domain_id=domain_id
        )
    )
    vendor_ids_present = {obs.vendor_id for obs in observations}
    facts_by_vendor = {
        vid: PartPricePolicy.facts_for(part_id=part.id, vendor_id=vid, domain_ids=domain_ids)
        for vid in vendor_ids_present
    }
    return render(
        request,
        f"{TEMPLATE_DIR}/part_history.html",
        {
            "part": part,
            "observations": observations,
            "facts_by_vendor": facts_by_vendor,
            "filters": {"vendor_id": vendor_id, "domain_id": domain_id},
            "vendors": Vendor.objects.filter(is_active=True).order_by("name"),
            "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
            "can_establish": can_establish_price(request),
        },
    )


def _verify_observation(request: HttpRequest, *, part, domain_ids: list[int]) -> HttpResponse:
    """D89: verifying appends a verified row — it never edits the row it was
    clicked on."""
    if not can_establish_price(request):
        raise PermissionDenied("Verifying a price requires the price_establish permission.")

    source = PartPriceObservation.objects.filter(
        pk=parse_int(request.POST.get("observation_id")), part=part
    ).first()
    if source is None:
        raise Http404

    try:
        PartPriceObservationFactory.create(
            part_id=part.id,
            vendor_id=source.vendor_id,
            domain_id=source.domain_id,
            unit_cost=source.unit_cost,
            quantity=source.quantity,
            currency=source.currency,
            observed_at=source.observed_at,
            source_type=source.source_type,
            confidence=source.confidence,
            is_verified=True,
            notes=f"Verified from observation #{source.pk}.",
            actor=request.user,
            visible_part_ids={part.id},
            visible_domain_ids=domain_ids,
            actor_can_establish=True,
        )
    except ProcurementValidationError as exc:
        for message in exc.errors:
            messages.error(request, message)
        return redirect(reverse("part_price_history", args=[part.id]))

    messages.success(request, f"Recorded ${source.unit_cost} as the established price.")
    return redirect(reverse("part_price_history", args=[part.id]))
