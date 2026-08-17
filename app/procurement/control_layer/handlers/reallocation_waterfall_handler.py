"""Handler: the priority + needed-by waterfall that reduces OPEN claims to
absorb a PO line's shortfall (reallocation_resolution_portal.md §7.1/§7.6).

Pure function — no DB writes, no query. Reuses OpenDemandSearch's tier
mapping rather than re-declaring a second ordering table; do not duplicate
that ranking anywhere else.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.models import DemandPriority

_TIER_RANK = {
    DemandPriority.CRITICAL: 0,
    DemandPriority.HIGH: 1,
    DemandPriority.MEDIUM: 2,
    DemandPriority.LOW: 3,
}


class ReallocationWaterfallHandler:
    @classmethod
    def allocate(cls, *, open_claims, shortfall: Decimal) -> dict[int, Decimal]:
        """`open_claims`: iterable of active, unlocked PurchaseOrderDemandLink
        rows (select_related("part_demand") already applied by the caller).

        Reduces from the BOTTOM of the priority order — Critical/soonest-
        needed is protected first, Low/latest-needed absorbs the cut first —
        then earliest-claimed (`created_at`) as the final tie-break (§7.6).

        Returns {link_id: new_quantity_allocated} for every open claim, untouched
        claims mapped to their existing value. Never reduces below zero and
        never touches a locked claim (the caller must not pass one in).
        """
        ordered = sorted(
            open_claims,
            key=lambda c: (
                _TIER_RANK.get(c.part_demand.priority, len(_TIER_RANK)),
                c.part_demand.needed_by is None,
                c.part_demand.needed_by,
                c.created_at,
            ),
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
