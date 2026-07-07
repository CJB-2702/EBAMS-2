"""Asset Relationships — group assets together in small sets (a tank under scuba
gear, a trailer under a truck). NOT a bill-of-materials tool.

Surfaces:
  - hub:    a searchable asset catalog (search-row-cards) routing to each asset's
            children view/edit.
  - view:   read-only nested child tree, depth-on-click expansion.
  - edit:   the same tree plus per-child detach and a search-to-attach bar.

Reads go through ``search/relationship_search``; all writes go through
``AssetContext(...).relationships`` (the single relationship write path).
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.control_layer.asset_context import AssetContext
from app.assets.control_layer.domain_structs.asset_hierarchy_struct import (
    AssetHierarchyStruct,
)
from app.assets.control_layer.domain_structs.asset_tree_struct import AssetTreeStruct
from app.assets.control_layer.guards.relationship_guard import RelationshipError
from app.assets.models import Asset, AssetClass
from app.assets.presentation_layer.search import relationship_search as search
from app.assets.presentation_layer.search.asset_search import load_asset_base

DEFAULT_DEPTH = 2


# ── Hub ──────────────────────────────────────────────────────────────────────
@require_http_methods(["GET"])
def asset_relationships_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    domain = request.GET.get("domain", "").strip()
    asset_class = request.GET.get("asset_class", "").strip()
    return render(request, "assets/relationships/hub.html", {
        "assets": search.search_relationship_assets(
            q=q, domain=domain, asset_class=asset_class
        ),
        "q": q,
        "domain": domain,
        "asset_class": asset_class,
        "domains": Domain.objects.order_by("name"),
        "classes": AssetClass.objects.order_by("name"),
    })


# ── View / Edit ──────────────────────────────────────────────────────────────
def _tree_context(asset: Asset, *, mode: str) -> dict:
    tree = AssetTreeStruct.from_asset(asset, max_depth=DEFAULT_DEPTH)
    hierarchy = AssetHierarchyStruct.from_asset(asset)
    return {
        "asset": asset,
        "tree": tree,
        "ancestors": hierarchy.ancestors,
        "mode": mode,
    }


@require_http_methods(["GET"])
def children_view(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    return render(request, "assets/relationships/view.html", _tree_context(asset, mode="view"))


@require_http_methods(["GET"])
def children_edit(request: HttpRequest, asset_id: int) -> HttpResponse:
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    return render(request, "assets/relationships/edit.html", _tree_context(asset, mode="edit"))


# ── HTMX fragments ───────────────────────────────────────────────────────────
@require_http_methods(["GET"])
def children_expand(request: HttpRequest, asset_id: int) -> HttpResponse:
    """Load one more depth of children beneath ``node`` (an asset id in the tree)."""
    node_id = request.GET.get("node", "").strip()
    mode = request.GET.get("mode", "view").strip()
    if not node_id.isdigit():
        raise Http404
    subtree = AssetTreeStruct.from_id(int(node_id), max_depth=1)
    if subtree is None:
        raise Http404
    return render(request, "assets/relationships/_tree_nodes.html", {
        "nodes": subtree.level(1),
        "mode": mode,
        "asset_id": asset_id,
        "can_detach": False,  # deeper rings are not direct children of the subject
    })


@require_http_methods(["GET"])
def children_search(request: HttpRequest, asset_id: int) -> HttpResponse:
    """Attachable-asset search results for the attach bar."""
    asset = load_asset_base(asset_id)
    if asset is None:
        raise Http404
    q = request.GET.get("q", "").strip()
    candidates = search.search_attachable_assets(asset, q=q) if q else []
    return render(request, "assets/relationships/_search_results.html", {
        "candidates": candidates,
        "asset_id": asset_id,
        "q": q,
    })


# ── Writes (single path: AssetContext.relationships) ─────────────────────────
@require_http_methods(["POST"])
def children_attach(request: HttpRequest, asset_id: int) -> HttpResponse:
    if load_asset_base(asset_id) is None:
        raise Http404
    raw = request.POST.get("child_id", "").strip()
    if not raw.isdigit():
        messages.error(request, "No asset selected to attach.")
        return redirect(reverse("children_edit", kwargs={"asset_id": asset_id}))
    try:
        AssetContext(asset_id, actor=request.user).relationships.attach_child(int(raw))
        messages.success(request, "Asset attached.")
    except (RelationshipError, ObjectDoesNotExist, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect(reverse("children_edit", kwargs={"asset_id": asset_id}))


@require_http_methods(["POST"])
def children_detach(request: HttpRequest, asset_id: int) -> HttpResponse:
    if load_asset_base(asset_id) is None:
        raise Http404
    raw = request.POST.get("child_id", "").strip()
    if not raw.isdigit():
        messages.error(request, "No child selected to detach.")
        return redirect(reverse("children_edit", kwargs={"asset_id": asset_id}))
    try:
        AssetContext(asset_id, actor=request.user).relationships.detach_child(int(raw))
        messages.success(request, "Asset detached.")
    except (RelationshipError, ObjectDoesNotExist, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect(reverse("children_edit", kwargs={"asset_id": asset_id}))
