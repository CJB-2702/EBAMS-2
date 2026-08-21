"""Struct: the discrepancy report's read model (intake_portal_workflow.md
§7.4, §11.2).

THERE IS NO DISCREPANCY TABLE, and there will not be one. A discrepancy is not
a record — it is THE DIFFERENCE BETWEEN TWO NUMBERS YOU ALREADY HAVE:

| Question               | Answer                                            |
| :--------------------- | :------------------------------------------------ |
| Is this line short?    | sum(allocations to line) < line.quantity          |
| Is there excess?       | allocations for this part with shipment_line NULL |
| How much was rejected? | sum(allocations to line where condition=rejected) |
| Who needs to look?     | Nobody is assigned. It is simply visible.         |

EVERYTHING IS A LIVE MIRROR. Derived fresh on every read, across all sessions
(§5.5). Nothing is stored, so nothing can drift, and there is nothing to
invalidate when a link changes.

NOTHING HERE IS ACTIONABLE. There is no resolution type, no acceptance, no
sign-off, and no status (§7.1). Nobody ever declares a discrepancy handled.
The system prevents the one thing it can prevent — over-allocation — surfaces
everything else, and leaves it visible until a person chooses to act. This
does kick the can down the road, and that is accepted: what the system
guarantees is that a discrepancy is never HIDDEN and never INVALID.

Netting is impossible by construction. Grouping is per part number for the
human reading it, but every figure underneath is per LINE, so a shortage on
one vendor's shipment can never cancel an overage on another's.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum

from app.inventory.control_layer.domain_structs.shipment_line_truth_struct import (
    ZERO,
    ShipmentLineTruthStruct,
)
from app.inventory.models.intake.enums import AllocationCondition


@dataclass(frozen=True)
class PartDiscrepancyStruct:
    """One card on the discrepancy report — one part number."""

    part_id: int
    part_number: str
    part_name: str
    lines: tuple[ShipmentLineTruthStruct, ...] = field(default_factory=tuple)
    unlinked_good: Decimal = ZERO
    unlinked_rejected: Decimal = ZERO

    @property
    def expected(self) -> Decimal:
        return sum((line.expected for line in self.lines), ZERO)

    @property
    def received(self) -> Decimal:
        return sum((line.linked_total for line in self.lines), ZERO)

    @property
    def rejected(self) -> Decimal:
        return sum((line.linked_rejected for line in self.lines), ZERO)

    @property
    def shortage(self) -> Decimal:
        """Summed PER LINE and only then totalled, never computed from the
        part-level totals — that would net one line's shortage against
        another's fullness and report a lie."""
        return sum((line.shortage for line in self.lines), ZERO)

    @property
    def unlinked_total(self) -> Decimal:
        return self.unlinked_good + self.unlinked_rejected

    @property
    def has_discrepancy(self) -> bool:
        return self.shortage > ZERO or self.rejected > ZERO or self.unlinked_total > ZERO

    @property
    def placeable(self) -> Decimal:
        """Unlinked stock that would actually fit somewhere on this part's
        lines. What the allocation portal could absorb right now — the number
        that makes the link out to it worth following."""
        capacity = sum((line.remaining_capacity for line in self.lines), ZERO)
        return min(self.unlinked_total, capacity)

    @property
    def severity(self) -> str:
        if self.shortage > ZERO and self.unlinked_total > ZERO:
            return "mixed"
        if self.unlinked_total > ZERO:
            return "excess"
        if self.shortage > ZERO:
            return "shortage"
        if self.rejected > ZERO:
            return "rejected"
        return "clean"


@dataclass(frozen=True)
class DiscrepancyReportStruct:
    intake_session_id: int
    parts: tuple[PartDiscrepancyStruct, ...] = field(default_factory=tuple)

    @property
    def flagged(self) -> tuple[PartDiscrepancyStruct, ...]:
        return tuple(p for p in self.parts if p.has_discrepancy)

    @property
    def is_clean(self) -> bool:
        return not self.flagged

    @classmethod
    def load(cls, *, session) -> "DiscrepancyReportStruct":
        from app.parts.models import Part

        truths = ShipmentLineTruthStruct.for_session(session=session)

        by_part: dict[int, list] = {}
        for truth in truths:
            by_part.setdefault(truth.part_id, []).append(truth)

        unlinked_rows = (
            session.allocations.filter(
                deleted_at__isnull=True, shipment_line__isnull=True
            )
            .values("part_id", "condition")
            .annotate(qty=Sum("quantity"))
        )
        unlinked: dict[int, dict] = {}
        for row in unlinked_rows:
            bucket = unlinked.setdefault(row["part_id"], {"good": ZERO, "rejected": ZERO})
            key = "good" if row["condition"] == AllocationCondition.GOOD else "rejected"
            bucket[key] += row["qty"] or ZERO

        part_ids = set(by_part) | set(unlinked)
        parts_by_id = {
            p.pk: p for p in Part.objects.filter(pk__in=part_ids)
        }

        cards = []
        for part_id in part_ids:
            part = parts_by_id.get(part_id)
            pool = unlinked.get(part_id, {"good": ZERO, "rejected": ZERO})
            cards.append(
                PartDiscrepancyStruct(
                    part_id=part_id,
                    part_number=part.part_number if part else "",
                    part_name=part.name if part else "",
                    lines=tuple(by_part.get(part_id, [])),
                    unlinked_good=pool["good"],
                    unlinked_rejected=pool["rejected"],
                )
            )
        return cls(
            intake_session_id=session.pk,
            parts=tuple(sorted(cards, key=lambda c: c.part_number)),
        )
