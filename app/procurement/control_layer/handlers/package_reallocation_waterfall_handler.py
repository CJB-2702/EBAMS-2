"""Handler: the Package↔PO Domain's own priority + needed-by waterfall
(Phase 5's independent mirror of ReallocationWaterfallHandler — no shared code
or state with the Demand↔PO Domain, per build_plan.md's guardrail).

JUDGMENT CALL, DOCUMENTED (kit phase_5 README does not specify this): a
PurchaseOrderShipmentLink claims against a PO LINE, not a demand, and a PO
line carries no priority or needed_by of its own — those live on PartDemand.
This handler derives a claim's effective priority/needed_by from the highest-
priority ACTIVE demand link on the claimed PO line (soonest needed_by on a
tie), falling back to the lowest priority tier with no needed_by when the PO
line carries no demand links at all (proactive/bulk stock — nothing urgent is
waiting on it). This is the same tier ranking OpenDemandSearch/
ReallocationWaterfallHandler use; it is not re-declared, only re-applied to a
different claim shape.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.models import DemandPriority, PurchaseOrderDemandLink

_TIER_RANK = {
    DemandPriority.CRITICAL: 0,
    DemandPriority.HIGH: 1,
    DemandPriority.MEDIUM: 2,
    DemandPriority.LOW: 3,
}
_LOWEST_TIER_RANK = len(_TIER_RANK)


class PackageReallocationWaterfallHandler:
    @classmethod
    def allocate(cls, *, open_claims, shortfall: Decimal) -> dict[int, Decimal]:
        """`open_claims`: iterable of active, unlocked PurchaseOrderShipmentLink
        rows (select_related("purchase_order_line") already applied).

        Returns {link_id: new_quantity_allocated}, reducing from the bottom of
        the effective priority order first, mirroring
        ReallocationWaterfallHandler.allocate exactly in shape.
        """
        claims = list(open_claims)
        priority_by_line = cls._effective_priority(
            line_ids=[c.purchase_order_line_id for c in claims]
        )

        ordered = sorted(
            claims,
            key=lambda c: priority_by_line.get(
                c.purchase_order_line_id, (_LOWEST_TIER_RANK, True, None)
            )
            + (c.created_at,),
        )

        resolutions: dict[int, Decimal] = {c.pk: c.quantity_allocated for c in ordered}
        remaining = shortfall
        for claim in reversed(ordered):
            if remaining <= 0:
                break
            reducible = min(claim.quantity_allocated, remaining)
            resolutions[claim.pk] = claim.quantity_allocated - reducible
            remaining -= reducible
        return resolutions

    @staticmethod
    def _effective_priority(*, line_ids) -> dict[int, tuple]:
        """{po_line_id: (tier_rank, needed_by_is_none, needed_by)} — the most
        urgent active demand link on each line, or the lowest-urgency tuple
        for a line with none."""
        links = PurchaseOrderDemandLink.objects.filter(
            purchase_order_line_id__in=set(line_ids),
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("part_demand")

        best: dict[int, tuple] = {}
        for link in links:
            demand = link.part_demand
            candidate = (
                _TIER_RANK.get(demand.priority, _LOWEST_TIER_RANK),
                demand.needed_by is None,
                demand.needed_by,
            )
            current = best.get(link.purchase_order_line_id)
            if current is None or candidate < current:
                best[link.purchase_order_line_id] = candidate
        return best
