"""Event list / detail / create / edit / soft-delete entrypoints."""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.events.control_layer.event_context import EventContext
from app.events.control_layer.handlers.event_handler import EventHandler
from app.events.models import Event, EventPriority, EventStatus, EventType
from app.events.presentation_layer.search.event_search import list_events_for_user
from app.events.presentation_layer.tools.file_previews import build_comments_context
from app.utils.hashids import decode_hash, encode_id

# Cards per page for the expanded (large) infinite-scroll view.
CARDS_PER_PAGE = 8


def build_event_card(event: Event, user) -> dict:
    """Context for a single expanded event card: metadata + comments."""
    ctx = EventContext(event.pk, user)
    return {
        "event": event,
        "hash": encode_id(event.pk),
        "comments": build_comments_context(ctx.struct),
    }


def _resolve_event(hash_str: str) -> Event:
    event_id = decode_hash(hash_str)
    if event_id is None:
        raise Http404
    return get_object_or_404(Event.objects.active().select_related("domain", "created_by"), pk=event_id)


def _check_domain_access(request, event: Event) -> bool:
    return event.domain_id in request.user.get_all_domain_ids() or event.created_by == request.user


@require_http_methods(["GET"])
def event_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("event_type", "").strip()
    asset_filter = request.GET.get("asset", "").strip()

    qs = list_events_for_user(request.user)
    if q:
        qs = qs.filter(title__icontains=q)
    if status_filter:
        qs = qs.filter(status=status_filter)
    if type_filter:
        qs = qs.filter(event_type=type_filter)

    asset = None
    if asset_filter.isdigit():
        from app.assets.models import Asset

        asset = Asset.objects.filter(pk=int(asset_filter)).first()
        qs = qs.filter(asset_links__asset_id=int(asset_filter)).distinct()

    fmt = request.GET.get("format", "").strip()

    # Querystring carrying just the active filters (no page / format) so the
    # density switch and infinite-scroll sentinel can preserve filter state.
    filter_params = {k: v for k, v in (
        ("q", q),
        ("status", status_filter),
        ("event_type", type_filter),
        ("asset", asset_filter),
    ) if v}
    base_query = urlencode(filter_params)

    shared = {
        "q": q,
        "status_filter": status_filter,
        "type_filter": type_filter,
        "asset_filter": asset_filter,
        "asset": asset,
        "base_query": base_query,
        "status_choices": EventStatus.choices,
        "type_choices": EventType.choices,
        "current_format": fmt or "condensed",
    }

    # ── Expanded card view + its infinite-scroll fragment ──
    if fmt in ("large", "htmx-event-cards"):
        page_obj = Paginator(qs, CARDS_PER_PAGE).get_page(request.GET.get("page"))
        cards = [build_event_card(e, request.user) for e in page_obj]
        card_ctx = {**shared, "current_format": "large", "cards": cards, "page_obj": page_obj}
        if fmt == "htmx-event-cards":
            return render(request, "events/fragments/event_cards_page.html", card_ctx)
        return render(request, "events/ev_list_large.html", card_ctx)

    events_with_hash = [{"event": e, "hash": encode_id(e.pk)} for e in qs]

    # ── Medium view: richer full-width rows ──
    if fmt == "medium":
        return render(request, "events/ev_list_medium.html", {
            **shared, "events_with_hash": events_with_hash,
        })

    # ── Condensed (default): flat table ──
    return render(request, "events/ev_list.html", {
        **shared, "events_with_hash": events_with_hash,
    })


@require_http_methods(["GET", "POST"])
def event_create(request: HttpRequest) -> HttpResponse:
    from django.utils import timezone

    from app.administration.models.data_ownership.domains import Domain

    user_domains = Domain.objects.filter(
        pk__in=request.user.get_all_domain_ids()
    ).order_by("name")

    now_default = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    if request.method == "POST":
        handler = EventHandler(request.user)
        result = handler.create(request.POST)
        if result.ok:
            messages.success(request, f"Event '{result.event.title}' created.")
            return redirect(reverse("event_detail", kwargs={"hash": encode_id(result.event.pk)}))
        return render(request, "events/ev_create.html", {
            "errors": result.errors,
            "form_data": request.POST,
            "user_domains": user_domains,
            "now_default": now_default,
            "status_choices": EventStatus.choices,
            "type_choices": EventType.choices,
            "priority_choices": EventPriority.choices,
        })

    return render(request, "events/ev_create.html", {
        "user_domains": user_domains,
        "now_default": now_default,
        "status_choices": EventStatus.choices,
        "type_choices": EventType.choices,
        "priority_choices": EventPriority.choices,
    })


@require_http_methods(["GET"])
def event_detail(request: HttpRequest, hash: str) -> HttpResponse:
    event = _resolve_event(hash)
    if not _check_domain_access(request, event):
        return HttpResponseForbidden("You do not have access to this event.")

    ctx = EventContext(event.pk, request.user)
    comments_context = build_comments_context(ctx.struct)

    can_edit = (
        event.created_by == request.user
        or request.user.has_perm("events.can_edit_others_events")
    )
    can_delete = request.user.has_perm("events.can_delete_any_event") or (
        event.created_by == request.user
        and not any(
            row["comment"].is_human_made and row["comment"].created_by != request.user
            for row in comments_context
        )
    )

    return render(request, "events/ev_detail.html", {
        "event": event,
        "event_hash": hash,
        "comments_context": comments_context,
        "can_edit": can_edit,
        "can_delete": can_delete,
    })


@require_http_methods(["GET", "POST"])
def event_edit(request: HttpRequest, hash: str) -> HttpResponse:
    event = _resolve_event(hash)

    can_edit = (
        event.created_by == request.user
        or request.user.has_perm("events.can_edit_others_events")
    )
    if not can_edit:
        return HttpResponseForbidden("You may not edit this event.")

    if request.method == "POST":
        result = EventHandler(request.user).edit(event, request.POST)
        if result.ok:
            messages.success(request, "Event updated.")
            return redirect(reverse("event_detail", kwargs={"hash": hash}))
        return render(request, "events/ev_edit.html", {
            "event": event,
            "event_hash": hash,
            "errors": result.errors,
            "status_choices": EventStatus.choices,
            "type_choices": EventType.choices,
            "priority_choices": EventPriority.choices,
        })

    return render(request, "events/ev_edit.html", {
        "event": event,
        "event_hash": hash,
        "status_choices": EventStatus.choices,
        "type_choices": EventType.choices,
        "priority_choices": EventPriority.choices,
    })


@require_http_methods(["POST"])
def event_soft_delete(request: HttpRequest, hash: str) -> HttpResponse:
    event = _resolve_event(hash)

    from app.events.presentation_layer.search.event_search import list_comments_for_event
    has_others_comments = list_comments_for_event(event).filter(
        is_human_made=True
    ).exclude(created_by=request.user).exists()

    can_delete = (
        request.user.has_perm("events.can_delete_any_event")
        or (event.created_by == request.user and not has_others_comments)
    )
    if not can_delete:
        messages.error(request, "You may not delete this event.")
        return redirect(reverse("event_detail", kwargs={"hash": hash}))

    EventContext(event.pk, request.user).delete()
    messages.success(request, f"Event '{event.title}' deleted.")
    return redirect(reverse("event_index"))
