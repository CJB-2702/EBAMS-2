"""PartPricePolicy — D91's two facts, resolved in bulk.

`facts_for_many` must be O(1) queries in the number of lines: a chip per
line rendered by a per-line policy call is exactly the mistake this kit was
written to avoid. Three bulk queries total (recorded, verified, other-vendor
count), resolved into a dict in Python — never a query per part.

Domain filtering happens before ordering, on every query, per §2 rule 7:
domain scoping is a security boundary, not a ranking preference.
"""

from __future__ import annotations

from django.db.models import Count, Q

from app.procurement.control_layer.domain_structs.part_price_facts_struct import (
    PartPriceFactsStruct,
    PriceFact,
)
from app.procurement.models import PartPriceObservation


class PartPricePolicy:
    @classmethod
    def facts_for(
        cls, *, part_id: int, vendor_id: int, domain_ids: list[int]
    ) -> PartPriceFactsStruct:
        return cls.facts_for_many(
            part_ids=[part_id], vendor_id=vendor_id, domain_ids=domain_ids
        )[part_id]

    @classmethod
    def facts_for_many(
        cls, *, part_ids: list[int], vendor_id: int, domain_ids: list[int]
    ) -> dict[int, PartPriceFactsStruct]:
        if not part_ids:
            return {}

        recorded_by_part = cls._first_per_part(
            PartPriceObservation.objects.filter(
                part_id__in=part_ids, vendor_id=vendor_id, domain_id__in=domain_ids
            )
            .select_related("vendor", "domain", "created_by")
            .order_by("part_id", "-observed_at", "-created_at")
        )
        verified_by_part = cls._first_per_part(
            PartPriceObservation.objects.filter(
                part_id__in=part_ids,
                vendor_id=vendor_id,
                domain_id__in=domain_ids,
                is_verified=True,
            )
            .select_related("vendor", "domain", "created_by")
            .order_by("part_id", "-observed_at", "-created_at")
        )
        counts_by_part = {
            row["part_id"]: row
            for row in (
                PartPriceObservation.objects.filter(
                    part_id__in=part_ids, domain_id__in=domain_ids
                )
                .values("part_id")
                .annotate(
                    total=Count("pk"),
                    other_vendor=Count("pk", filter=~Q(vendor_id=vendor_id)),
                )
            )
        }

        return {
            part_id: PartPriceFactsStruct(
                part_id=part_id,
                vendor_id=vendor_id,
                most_recent=cls._to_fact(recorded_by_part.get(part_id)),
                most_recent_verified=cls._to_fact(verified_by_part.get(part_id)),
                other_vendor_count=counts_by_part.get(part_id, {}).get("other_vendor", 0),
                total_count=counts_by_part.get(part_id, {}).get("total", 0),
            )
            for part_id in part_ids
        }

    @staticmethod
    def _first_per_part(qs) -> dict[int, PartPriceObservation]:
        """`qs` is ordered by part_id, -observed_at, -created_at — the first
        row seen per part_id is its most recent, in one pass."""
        first: dict[int, PartPriceObservation] = {}
        for row in qs:
            first.setdefault(row.part_id, row)
        return first

    @staticmethod
    def _to_fact(row: PartPriceObservation | None) -> PriceFact | None:
        if row is None:
            return None
        return PriceFact(
            observation_id=row.pk,
            unit_cost=row.unit_cost,
            quantity=row.quantity,
            observed_at=row.observed_at,
            source_type=row.source_type,
            confidence=row.confidence,
            is_verified=row.is_verified,
            vendor_id=row.vendor_id,
            vendor_name=row.vendor.name,
            domain_id=row.domain_id,
            domain_name=row.domain.name,
            recorded_by_name=str(row.created_by) if row.created_by_id else "",
        )
