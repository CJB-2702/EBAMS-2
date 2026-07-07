"""Read helpers for asset-class list / detail screens.

The list spans the class plus its domains, models, and assets (counts) — well past
the two-table inline threshold — so the query lives here behind ``search/``.
"""

from __future__ import annotations

from django.db.models import Count, QuerySet

from app.assets.models import AssetClass


def search_asset_classes(
    *, q: str = "", category: str = "", domain: str = ""
) -> QuerySet[AssetClass]:
    qs = (
        AssetClass.objects.prefetch_related("domains")
        .annotate(
            model_count=Count("models", distinct=True),
            asset_count=Count("assets", distinct=True),
        )
        .order_by("name")
    )

    q = (q or "").strip()
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(category__icontains=q)
        qs = qs.distinct()
    if category:
        qs = qs.filter(category=category)
    if domain:
        qs = qs.filter(domains__id=domain)

    return qs


def load_asset_class_detail(class_id: int) -> AssetClass | None:
    return (
        AssetClass.objects.prefetch_related(
            "domains", "capability_links__capability_definition"
        )
        .annotate(
            model_count=Count("models", distinct=True),
            asset_count=Count("assets", distinct=True),
        )
        .filter(id=class_id)
        .first()
    )


def list_categories() -> list[str]:
    return sorted(
        AssetClass.objects.exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
    )
