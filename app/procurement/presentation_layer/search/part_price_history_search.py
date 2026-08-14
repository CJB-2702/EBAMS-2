"""Search: one part's price observations, across all vendors, restricted to
the actor's visible domains. Backs the full history page and D92's picker.
"""

from __future__ import annotations

from django.db.models import QuerySet

from app.procurement.models import PartPriceObservation


class PartPriceHistorySearch:
    @classmethod
    def for_part(
        cls,
        *,
        part_id: int,
        domain_ids: list[int],
        vendor_id: int | None = None,
        domain_id: int | None = None,
        limit: int | None = None,
    ) -> QuerySet[PartPriceObservation]:
        qs = (
            PartPriceObservation.objects.filter(part_id=part_id, domain_id__in=domain_ids)
            .select_related("vendor", "domain", "created_by", "source_po_line")
            .order_by("-observed_at", "-created_at")
        )
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if limit:
            qs = qs[:limit]
        return qs
