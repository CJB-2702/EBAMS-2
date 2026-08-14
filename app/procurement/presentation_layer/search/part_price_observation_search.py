"""Search: every price observation visible to the actor, filterable by part,
vendor, domain, source, confidence, verification, and date range. Backs the
price hub's search page (price_hub, /procurement/prices/).

Domain filtering is applied first, as a security boundary (§2 rule 7 of
build_plan.md) — every other filter narrows what is already visible, never
what makes it visible.
"""

from __future__ import annotations

from datetime import date

from django.db.models import Q, QuerySet

from app.procurement.models import PartPriceObservation


class PartPriceObservationSearch:
    @classmethod
    def results(
        cls,
        *,
        domain_ids: list[int],
        q: str = "",
        vendor_id: int | None = None,
        domain_id: int | None = None,
        source_type: str = "",
        confidence: str = "",
        is_verified: str = "",
        observed_from: date | None = None,
        observed_to: date | None = None,
    ) -> QuerySet[PartPriceObservation]:
        qs = PartPriceObservation.objects.filter(domain_id__in=domain_ids).select_related(
            "part", "vendor", "domain", "created_by"
        )

        if q:
            qs = qs.filter(
                Q(part__part_number__icontains=q)
                | Q(part__name__icontains=q)
                | Q(vendor__name__icontains=q)
            )
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if source_type:
            qs = qs.filter(source_type=source_type)
        if confidence:
            qs = qs.filter(confidence=confidence)
        if is_verified == "verified":
            qs = qs.filter(is_verified=True)
        elif is_verified == "unverified":
            qs = qs.filter(is_verified=False)
        if observed_from:
            qs = qs.filter(observed_at__gte=observed_from)
        if observed_to:
            qs = qs.filter(observed_at__lte=observed_to)

        return qs.order_by("-observed_at", "-created_at")
