"""D91's two facts, no ranking. Replaces the pre-D87 three-rung ladder
(build_plan.md §1.2) — the policy returns the PO's-vendor's most recent
recorded and most recent verified observation, and nothing decides which one
"wins". A human resolves the disagreement in half a second; the chip just
shows the two dated facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class PriceFact:
    observation_id: int
    unit_cost: Decimal
    quantity: Decimal | None
    observed_at: date
    source_type: str
    confidence: str
    is_verified: bool
    vendor_id: int
    vendor_name: str
    domain_id: int
    domain_name: str
    recorded_by_name: str

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "unit_cost": str(self.unit_cost),
            "quantity": str(self.quantity) if self.quantity is not None else None,
            "observed_at": self.observed_at.isoformat(),
            "source_type": self.source_type,
            "confidence": self.confidence,
            "is_verified": self.is_verified,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "domain_id": self.domain_id,
            "domain_name": self.domain_name,
            "recorded_by_name": self.recorded_by_name,
        }


@dataclass(frozen=True)
class PartPriceFactsStruct:
    part_id: int
    vendor_id: int
    most_recent: PriceFact | None
    most_recent_verified: PriceFact | None
    #: Feeds the doorway when both facts above are None — "no price from this
    #: vendor" is not the same as "no price at all".
    other_vendor_count: int
    #: Every observation for this part, any vendor — the doorway's "N prices
    #: on record for this part" line when a same-vendor fact already exists.
    total_count: int

    def collapses(self) -> bool:
        """D91: if the most recent record IS the verified one, show one
        line — a chip that always shows two numbers trains people to stop
        reading it."""
        if self.most_recent is None or self.most_recent_verified is None:
            return False
        return self.most_recent.observation_id == self.most_recent_verified.observation_id

    def has_any(self) -> bool:
        return self.most_recent is not None or self.most_recent_verified is not None

    def to_dict(self) -> dict:
        return {
            "part_id": self.part_id,
            "vendor_id": self.vendor_id,
            "most_recent": self.most_recent.to_dict() if self.most_recent else None,
            "most_recent_verified": (
                self.most_recent_verified.to_dict() if self.most_recent_verified else None
            ),
            "other_vendor_count": self.other_vendor_count,
            "total_count": self.total_count,
            "collapses": self.collapses(),
        }
