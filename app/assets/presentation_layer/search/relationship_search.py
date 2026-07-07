"""Reads for the asset-relationship screens.

Two queries: the hub catalog (every asset, annotated with its direct-child count,
for the search-row-card list) and the attach candidates for one asset (everything
attachable under it — excluding itself, its existing direct children, and its
ancestors). Pure reads; the authoritative structural guard stays in
``RelationshipPolicy`` at attach time.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet

from app.assets.models import Asset


def _base_queryset() -> QuerySet[Asset]:
    return (
        Asset.objects.select_related("asset_class", "model", "domain", "parent_asset")
        .annotate(direct_child_count=Count("children", distinct=True))
        .order_by("name")
    )


def _apply_text(qs: QuerySet[Asset], q: str) -> QuerySet[Asset]:
    q = (q or "").strip()
    if q:
        qs = (qs.filter(name__icontains=q) | qs.filter(serial_number__icontains=q)).distinct()
    return qs


def search_relationship_assets(
    *, q: str = "", domain: str = "", asset_class: str = ""
) -> QuerySet[Asset]:
    """Hub catalog: assets annotated with ``direct_child_count`` for the row cards."""
    qs = _apply_text(_base_queryset(), q)
    if domain:
        qs = qs.filter(domain_id=domain)
    if asset_class:
        qs = qs.filter(asset_class_id=asset_class)
    return qs


def _ancestor_ids(asset: Asset) -> set[int]:
    ids: set[int] = set()
    node = asset.parent_asset
    while node is not None and node.id not in ids:
        ids.add(node.id)
        node = node.parent_asset
    return ids


def search_attachable_assets(asset: Asset, *, q: str = "", limit: int = 20) -> list[Asset]:
    """Assets that can be attached under ``asset``. Excludes the asset itself, its
    existing direct children, and its ancestors. Deeper-cycle attempts are caught
    authoritatively by ``RelationshipPolicy`` on attach."""
    exclude_ids: set[int] = {asset.id}
    exclude_ids |= set(
        Asset.objects.filter(parent_asset_id=asset.id).values_list("id", flat=True)
    )
    exclude_ids |= _ancestor_ids(asset)

    qs = _apply_text(_base_queryset(), q).exclude(id__in=exclude_ids)
    return list(qs[:limit])
