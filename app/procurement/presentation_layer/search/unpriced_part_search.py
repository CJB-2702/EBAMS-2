"""Search: parts with zero visible price observations — the D86 correctness
backstop, not a convenience. Viewer-relative per D87: a part priced only for
East Coast is unpriced for a West-only actor, and that is intentional.
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, QuerySet

from app.parts.models import Part
from app.procurement.models import PartPriceObservation
from app.procurement.presentation_layer.search.part_visibility import visible_parts_qs


class UnpricedPartSearch:
    @classmethod
    def results(
        cls,
        *,
        domain_ids: list[int],
        domain_id: int | None = None,
        created_from=None,
        part_type: str = "",
        q: str = "",
    ) -> QuerySet[Part]:
        qs = cls._base(domain_ids=domain_ids)

        if domain_id:
            qs = qs.filter(
                domain_access_mappings__domain_id=domain_id,
                domain_access_mappings__is_active=True,
            )
        if created_from:
            qs = qs.filter(created_at__gte=created_from)
        if part_type:
            qs = qs.filter(part_type=part_type)
        if q:
            qs = qs.filter(part_number__icontains=q)

        return qs.order_by("created_at").prefetch_related("domain_access_mappings__domain")

    @classmethod
    def count(cls, *, domain_ids: list[int]) -> int:
        return cls._base(domain_ids=domain_ids).count()

    @staticmethod
    def _base(*, domain_ids: list[int]) -> QuerySet[Part]:
        visible_observation = PartPriceObservation.objects.filter(
            part=OuterRef("pk"), domain_id__in=domain_ids
        )
        return visible_parts_qs(domain_ids=domain_ids).filter(
            ~Exists(visible_observation)
        )
