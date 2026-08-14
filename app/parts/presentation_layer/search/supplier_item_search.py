"""search_supplier_items — the supplier item hub's filter bar. Independent,
narrowing criteria: mpn (vendor part number), name, manufacturer, and
part_number (the internal Part it's mapped to)."""

from __future__ import annotations

from django.db.models import QuerySet

from app.parts.models import SupplierItem


def search_supplier_items(
    *,
    mpn: str = "",
    name: str = "",
    manufacturer: str = "",
    part_number: str = "",
) -> QuerySet[SupplierItem]:
    qs = SupplierItem.objects.select_related("part_manufacturer", "internal_part")

    mpn = (mpn or "").strip()
    if mpn:
        qs = qs.filter(manufacturer_part_number__icontains=mpn)
    if name:
        qs = qs.filter(name__icontains=name)
    if manufacturer:
        qs = qs.filter(part_manufacturer__name__icontains=manufacturer)
    if part_number:
        qs = qs.filter(internal_part__part_number__icontains=part_number)

    return qs
