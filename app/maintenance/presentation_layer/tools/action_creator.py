"""The Action Creator Portal's source list and per-source data.

Two hosts render the same five sources — the event edit portal and the
template builder — and both used to carry their own half of it: the edit
portal had all five with no model filter, the builder had three of them with
one. This module is the single implementation; a host supplies only its own
scope (which domains, which asset class/models, what "current" means) and
picks its own chrome (tab strip or select) in the partial.

Read-only. Lives in presentation_layer/tools because it shapes a view's
context and issues no writes.
"""

from __future__ import annotations

from django.db.models import Count, Q

from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.search.proto_action_search import (
    ProtoActionSearch,
)

#: Action Creator Portal sources, in display order. `template_set` is first
#: because "copy a whole procedure" is the commonest way a step list starts.
CREATOR_TABS = (
    ("template_set", "From Template"),
    ("template_action", "From Template Action"),
    ("proto", "From Proto Action"),
    ("current", "From Current Build"),
    ("blank", "Blank Action"),
)

CREATOR_TAB_VALUES = frozenset(value for value, _ in CREATOR_TABS)

#: Unfiltered (no `q` typed) listings are capped tight — just enough to show
#: the portal isn't empty and nudge toward the asset-scoped default, not a
#: full browse (that's what typing into the search box is for).
DEFAULT_LIMIT = 2
SEARCH_LIMIT = 25


def normalize_tab(raw: str | None) -> str:
    tab = (raw or "").strip()
    return tab if tab in CREATOR_TAB_VALUES else "template_set"


def creator_tab_context(
    *,
    tab: str,
    q: str,
    domain_ids,
    asset_class_id: int | None = None,
    asset_model_ids=None,
    used_on_model_id: int | None = None,
    current_actions=None,
) -> dict:
    """The data for one source body.

    Shared by the full page GET (so the initially-active source isn't empty on
    first load) and by the htmx switch fragment.

    `asset_class_id` / `asset_model_ids` scope the *unfiltered* default listing
    to what the host is about — an event's asset, or the template draft's own
    class. Typing a search term deliberately escapes that scope and browses the
    whole library.
    """
    asset_model_ids = list(asset_model_ids or [])
    context: dict = {}

    if tab == "template_set":
        qs = (
            TemplateActionSet.objects.filter(
                domain_id__in=domain_ids, deleted_at__isnull=True, is_active=True
            )
            .annotate(action_count=Count("template_action_items"))
            .prefetch_related("template_action_items")
        )
        if q:
            qs = qs.filter(Q(task_name__icontains=q) | Q(description__icontains=q))
            context["template_sets"] = qs.order_by("task_name")[:SEARCH_LIMIT]
        else:
            scoped, is_scoped = _scope(qs, asset_class_id, asset_model_ids, prefix="")
            rows = list(scoped.order_by("task_name")[:DEFAULT_LIMIT])
            context["template_sets"] = rows
            context["template_sets_asset_scoped"] = is_scoped and bool(rows)

    elif tab == "template_action":
        qs = TemplateActionItem.objects.filter(
            template_action_set__domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("template_action_set")
        if q:
            qs = qs.filter(Q(action_name__icontains=q) | Q(description__icontains=q))
            context["template_actions"] = qs.order_by("action_name")[:SEARCH_LIMIT]
        else:
            scoped, _ = _scope(
                qs, asset_class_id, asset_model_ids, prefix="template_action_set__"
            )
            context["template_actions"] = scoped.order_by("action_name")[:DEFAULT_LIMIT]

    elif tab == "proto":
        # Routed through ProtoActionSearch so the "used on model" filter the
        # template builder grew is available to both hosts, not just one.
        qs = ProtoActionSearch.library_pool(
            domain_ids=domain_ids, q=q, used_on_model_id=used_on_model_id
        )
        limit = SEARCH_LIMIT if (q or used_on_model_id) else DEFAULT_LIMIT
        context["proto_actions"] = qs[:limit]

    elif tab == "current":
        context["current_actions"] = current_actions or []

    return context


def _scope(qs, asset_class_id, asset_model_ids, *, prefix: str):
    """Narrow an unfiltered listing to the host's own asset scope.

    Returns (queryset, was_scoped) so the caller can tell the reader why the
    list is short — "matching this asset model" is a very different message
    from "the most recent in your domain".
    """
    clause = Q()
    if asset_model_ids:
        clause |= Q(**{f"{prefix}asset_models__in": asset_model_ids})
    if asset_class_id:
        clause |= Q(**{f"{prefix}asset_class_id": asset_class_id})
    if not clause:
        return qs, False
    return qs.filter(clause).distinct(), True

