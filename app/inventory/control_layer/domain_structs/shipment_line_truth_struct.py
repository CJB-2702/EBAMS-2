"""Struct: the shipment-line truth read model, and the two progress rollups
built on top of it.

THE SHIPMENT LINE IS THE UNIT OF TRUTH. THE SESSION IS A LENS ONTO IT
(intake_portal_workflow.md §5.5). Everything in this module reads from ALL
live allocations against a line — every non-cancelled, non-deleted session's
rows — and then splits that total into "this session" and "everyone else"
purely so the UI can dampen and lock the latter. The split is a display
concern. The arithmetic is never scoped to a session.

Scoping a quantity to one session is what manufactures phantom shortages:
session 2 opens showing a line at 0% received when session 1 already took 40
of 50, and the operator either panics or double-counts. It is also what would
break the over-allocation cap, since "already linked" has to mean "by anyone"
for the cap to mean anything.

Nothing here is stored. Discrepancies are derived fresh on every read (§11.2),
so nothing can drift and there is nothing to invalidate when a link changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Q, QuerySet, Sum

from app.inventory.models.intake.enums import AllocationCondition, IntakeSessionStatus
from app.inventory.models.intake.item_allocation import ItemAllocation

ZERO = Decimal("0")


def live_allocations_for_line(shipment_line_id: int) -> QuerySet[ItemAllocation]:
    """THE canonical "what is linked to this line" queryset. Every capacity
    check, progress bar, and discrepancy figure in the system goes through
    this one function, so the definition of "live" cannot drift between the
    thing that enforces the cap and the thing that displays it.

    Included: any live allocation, from any session, linked to the line.
    Excluded: soft-deleted allocations, and allocations belonging to a
    cancelled or soft-deleted session (§5.5, "Scope of other sessions").

    Allocations from another session that is still OPEN are included and
    counted, which means a bar can move backwards if that session deletes a
    row. That is accepted (Q19) — one treatment, no second shade.
    """
    return ItemAllocation.objects.filter(
        shipment_line_id=shipment_line_id,
        deleted_at__isnull=True,
        intake_session__deleted_at__isnull=True,
    ).exclude(intake_session__status=IntakeSessionStatus.CANCELLED)


def _totals(queryset) -> tuple[Decimal, Decimal]:
    agg = queryset.aggregate(
        good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
        rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
    )
    return agg["good"] or ZERO, agg["rejected"] or ZERO


@dataclass(frozen=True)
class ShipmentLineTruthStruct:
    """One shipment line, told truthfully — i.e. across every session."""

    shipment_line_id: int
    shipment_id: int
    shipment_number: str
    part_id: int
    part_number: str
    expected: Decimal

    # Across ALL sessions.
    linked_good: Decimal
    linked_rejected: Decimal

    # The same rows, split for display only.
    mine_good: Decimal
    mine_rejected: Decimal
    others_good: Decimal
    others_rejected: Decimal
    others_session_ids: tuple[int, ...] = field(default_factory=tuple)

    @property
    def linked_total(self) -> Decimal:
        return self.linked_good + self.linked_rejected

    @property
    def remaining_capacity(self) -> Decimal:
        """How much more may be linked before the ban bites (§7.2). Never
        negative: if procurement reduced the line below what is already
        allocated, the existing rows stand and capacity is simply zero."""
        return max(self.expected - self.linked_total, ZERO)

    @property
    def is_full(self) -> bool:
        return self.remaining_capacity <= ZERO

    @property
    def shortage(self) -> Decimal:
        """Expected minus everything received against the line. Zero when the
        line is satisfied or over — over is impossible by construction."""
        return max(self.expected - self.linked_total, ZERO)

    @property
    def has_discrepancy(self) -> bool:
        return self.shortage > ZERO or self.linked_rejected > ZERO

    @property
    def received_pct(self) -> float:
        if self.expected <= ZERO:
            return 0.0
        return float(min(self.linked_total / self.expected, Decimal("1")) * 100)

    @property
    def touched_by_others(self) -> bool:
        return bool(self.others_session_ids)

    @classmethod
    def for_line(cls, *, line, session_id: int | None = None) -> "ShipmentLineTruthStruct":
        allocations = live_allocations_for_line(line.pk)
        linked_good, linked_rejected = _totals(allocations)

        if session_id is None:
            mine_good = mine_rejected = ZERO
            others_good, others_rejected = linked_good, linked_rejected
            other_ids = allocations.values_list("intake_session_id", flat=True)
        else:
            mine_good, mine_rejected = _totals(
                allocations.filter(intake_session_id=session_id)
            )
            others = allocations.exclude(intake_session_id=session_id)
            others_good, others_rejected = _totals(others)
            other_ids = others.values_list("intake_session_id", flat=True)

        return cls(
            shipment_line_id=line.pk,
            shipment_id=line.shipment_id,
            shipment_number=line.shipment.shipment_number,
            part_id=line.part_id,
            part_number=line.part.part_number,
            expected=line.quantity or ZERO,
            linked_good=linked_good,
            linked_rejected=linked_rejected,
            mine_good=mine_good,
            mine_rejected=mine_rejected,
            others_good=others_good,
            others_rejected=others_rejected,
            others_session_ids=tuple(sorted(set(other_ids))),
        )

    @classmethod
    def for_session(cls, *, session) -> list["ShipmentLineTruthStruct"]:
        """Every line on every shipment this session receives against."""
        from app.procurement.models import ShipmentLine

        shipment_ids = list(
            session.shipment_associations.filter(deleted_at__isnull=True).values_list(
                "shipment_id", flat=True
            )
        )
        lines = (
            ShipmentLine.objects.filter(
                shipment_id__in=shipment_ids, deleted_at__isnull=True
            )
            .select_related("part", "shipment")
            .order_by("shipment_id", "id")
        )
        return [cls.for_line(line=line, session_id=session.pk) for line in lines]


@dataclass(frozen=True)
class PartProgressStruct:
    """One part number's progress on the RECORD page (§2.2, §3).

    Aggregated BY PART NUMBER across every associated shipment — part A on
    three shipments is ONE bar, because the operator counting boxes does not
    care which packing slip a screw belongs to.

    THE RECORD BAR ANSWERS "DID IT ALL SHOW UP?" — counted over expected. It
    reads 50% on a 25-of-50 shipment, and that is a vendor shortage, not a
    filing problem. Do not confuse it with the associate bar (§3); conflating
    the two is what made the original page incomprehensible.
    """

    part_id: int
    part_number: str
    part_name: str
    expected: Decimal
    counted_good: Decimal
    counted_rejected: Decimal
    unlinked: Decimal
    others_counted: Decimal
    line_count: int

    @property
    def counted_total(self) -> Decimal:
        return self.counted_good + self.counted_rejected

    @property
    def outstanding(self) -> Decimal:
        return max(self.expected - self.counted_total, ZERO)

    @property
    def counted_pct(self) -> float:
        if self.expected <= ZERO:
            return 0.0
        return float(min(self.counted_total / self.expected, Decimal("1")) * 100)

    @property
    def is_complete(self) -> bool:
        return self.expected > ZERO and self.counted_total >= self.expected

    @classmethod
    def for_session(cls, *, session) -> list["PartProgressStruct"]:
        from app.parts.models import Part

        truths = ShipmentLineTruthStruct.for_session(session=session)

        by_part: dict[int, dict] = {}
        for truth in truths:
            bucket = by_part.setdefault(
                truth.part_id,
                {
                    "part_number": truth.part_number,
                    "expected": ZERO,
                    "good": ZERO,
                    "rejected": ZERO,
                    "others": ZERO,
                    "lines": 0,
                },
            )
            bucket["expected"] += truth.expected
            bucket["good"] += truth.linked_good
            bucket["rejected"] += truth.linked_rejected
            bucket["others"] += truth.others_good + truth.others_rejected
            bucket["lines"] += 1

        # Unlinked rows have no line to hang off, so they are counted
        # separately — they are physically present and belong on the count.
        unlinked_rows = (
            session.allocations.filter(
                deleted_at__isnull=True, shipment_line__isnull=True
            )
            .values("part_id")
            .annotate(qty=Sum("quantity"))
        )
        unlinked_by_part = {r["part_id"]: r["qty"] or ZERO for r in unlinked_rows}

        part_ids = set(by_part) | set(unlinked_by_part)
        names = dict(
            Part.objects.filter(pk__in=part_ids).values_list("pk", "name")
        )
        numbers = dict(
            Part.objects.filter(pk__in=part_ids).values_list("pk", "part_number")
        )

        out = []
        for part_id in part_ids:
            bucket = by_part.get(part_id)
            unlinked = unlinked_by_part.get(part_id, ZERO)
            out.append(
                cls(
                    part_id=part_id,
                    part_number=numbers.get(part_id, ""),
                    part_name=names.get(part_id, ""),
                    expected=bucket["expected"] if bucket else ZERO,
                    counted_good=bucket["good"] if bucket else ZERO,
                    counted_rejected=bucket["rejected"] if bucket else ZERO,
                    unlinked=unlinked,
                    others_counted=bucket["others"] if bucket else ZERO,
                    line_count=bucket["lines"] if bucket else 0,
                )
            )
        return sorted(out, key=lambda p: p.part_number)


@dataclass(frozen=True)
class AssociateProgressStruct:
    """One part number's progress on the ASSOCIATE page (§2.3, §3).

    THE ASSOCIATE BAR ANSWERS "DID I FILE IT ALL?" — linked over COUNTED, not
    over expected. A 100% associate bar sitting next to a 50% record bar is a
    correct, complete, well-filed short shipment; the shortage is page 4's
    problem, not page 3's.

    The bar CANNOT EXCEED 100%, because a line can never be over-allocated
    (§7.2). Excess simply stays unlinked, and unlinked items are the
    allocation portal's business.
    """

    part_id: int
    part_number: str
    part_name: str
    counted: Decimal
    linked: Decimal
    unlinked: Decimal
    unmet_capacity: Decimal

    @property
    def linked_pct(self) -> float:
        if self.counted <= ZERO:
            return 100.0
        return float(min(self.linked / self.counted, Decimal("1")) * 100)

    @property
    def is_fully_filed(self) -> bool:
        return self.unlinked <= ZERO

    @classmethod
    def for_session(cls, *, session) -> list["AssociateProgressStruct"]:
        from app.parts.models import Part

        truths = ShipmentLineTruthStruct.for_session(session=session)
        capacity: dict[int, Decimal] = {}
        for truth in truths:
            capacity[truth.part_id] = (
                capacity.get(truth.part_id, ZERO) + truth.remaining_capacity
            )

        rows = (
            session.allocations.filter(deleted_at__isnull=True)
            .values("part_id")
            .annotate(
                total=Sum("quantity"),
                unlinked=Sum("quantity", filter=Q(shipment_line__isnull=True)),
            )
        )
        part_ids = {r["part_id"] for r in rows} | set(capacity)
        names = dict(Part.objects.filter(pk__in=part_ids).values_list("pk", "name"))
        numbers = dict(
            Part.objects.filter(pk__in=part_ids).values_list("pk", "part_number")
        )

        by_part = {r["part_id"]: r for r in rows}
        out = []
        for part_id in part_ids:
            row = by_part.get(part_id)
            counted = (row["total"] or ZERO) if row else ZERO
            unlinked = (row["unlinked"] or ZERO) if row else ZERO
            out.append(
                cls(
                    part_id=part_id,
                    part_number=numbers.get(part_id, ""),
                    part_name=names.get(part_id, ""),
                    counted=counted,
                    linked=counted - unlinked,
                    unlinked=unlinked,
                    unmet_capacity=capacity.get(part_id, ZERO),
                )
            )
        return sorted(out, key=lambda p: p.part_number)
