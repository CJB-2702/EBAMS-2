"""search_parts — the parts hub's filter bar. Five independent, narrowing
criteria: part_number (silently also matches aliases — internal/legacy/NSN/
vendor MPN — so a technician typing a vendor part number still lands on the
right Part), name, description, manufacturer, and revision_name."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.parts.models import Alias, Part


def search_parts(
    *,
    part_number: str = "",
    name: str = "",
    description: str = "",
    manufacturer: str = "",
    revision_name: str = "",
) -> QuerySet[Part]:
    qs = (
        Part.objects.select_related("primary_image__file")
        .prefetch_related("revisions")
        .order_by("part_number")
    )

    part_number = (part_number or "").strip()
    if part_number:
        alias_part_ids = Alias.objects.filter(
            normalized_value__icontains=part_number.casefold()
        ).values_list("part_id", flat=True)
        qs = qs.filter(Q(part_number__icontains=part_number) | Q(id__in=alias_part_ids))
    if name:
        qs = qs.filter(name__icontains=name)
    if description:
        qs = qs.filter(description__icontains=description)
    if manufacturer:
        qs = qs.filter(supplier_items__part_manufacturer__name__icontains=manufacturer)
    if revision_name:
        qs = qs.filter(
            Q(revisions__major_revision_name__icontains=revision_name)
            | Q(revisions__minor_revision_name__icontains=revision_name)
        )
    if manufacturer or revision_name:
        qs = qs.distinct()

    return qs
