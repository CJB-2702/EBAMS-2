"""Read helpers for manufacturer list / detail screens.

Encapsulates the filters and the ``models`` prefetch strategy so entrypoints stay
thin. The list spans two logical reads (manufacturer + its produced models for the
count column), which is the threshold at which the layer rules want the query
behind ``search/`` rather than inlined.
"""

from __future__ import annotations

from django.db.models import QuerySet

from app.assets.models import Manufacturer


def search_manufacturers(*, q: str = "", is_active: str = "") -> QuerySet[Manufacturer]:
    qs = Manufacturer.objects.prefetch_related("models").order_by("name")

    q = (q or "").strip()
    if q:
        qs = qs.filter(name__icontains=q) | qs.filter(code__icontains=q)
        qs = qs.distinct()

    if is_active in ("True", "False"):
        qs = qs.filter(is_active=(is_active == "True"))

    return qs


def load_manufacturer_detail(manufacturer_id: int) -> Manufacturer | None:
    """Return the manufacturer with its produced models (and classes) prefetched,
    or ``None`` if it does not exist."""
    return (
        Manufacturer.objects.prefetch_related("models__asset_class")
        .filter(id=manufacturer_id)
        .first()
    )
