"""Guard: may this demand's requested part be swapped for a different one?

Part substitution is the manager's answer to "we don't stock that, use this
instead" — the legacy maintenance approval queue's ``bulk-change-part``. It is
deliberately NOT one of the four state axes: swapping the part changes *what*
is being asked for, not where the ask has got to, so it writes no
PartDemandUpdate journal row.

That makes it dangerous in exactly one direction. ``PartDemand.part`` is
load-bearing on the graph: GraphSummaryManager._derive_part_id reads the part
off any member because a graph may never span parts, and
PurchaseOrderDemandLinkValidator's part-match rule is what makes that true.
Swapping the part on a demand that shares a graph with PO lines or shipment
lines would break that invariant silently.

So this policy refuses everything except the one genuinely safe case: a demand
nothing has happened to yet, sitting alone in its own single-member graph. In
that case the caller re-derives the graph (recalculate) and the invariant holds
because there was never anyone else in the graph to disagree with.

Every refusal names the thing that must happen first, never a generic failure
(shared_workflows.md §3).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandState,
    IssuanceState,
    PartDemand,
    PurchaseOrderDemandLink,
)

#: demand_state values from which a part may never be swapped. Terminal or
#: decided — changing the subject of a settled request rewrites history.
_LOCKED_DEMAND_STATES = frozenset(
    {DemandState.COMPLETED, DemandState.CANCELLED, DemandState.REJECTED}
)


@dataclass(frozen=True)
class SubstitutionVerdict:
    allowed: bool
    reason: str = ""


class PartDemandSubstitutionPolicy:
    @classmethod
    def decide(cls, *, demand: PartDemand, new_part_id: int) -> SubstitutionVerdict:
        if new_part_id == demand.part_id:
            return SubstitutionVerdict(
                allowed=False,
                reason=f"Demand #{demand.pk} already requests that part.",
            )

        if demand.demand_state in _LOCKED_DEMAND_STATES:
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} is {demand.get_demand_state_display()} — "
                    "raise a new demand for the replacement part instead."
                ),
            )

        if demand.purchasing_state != PURCHASING_STATE_UNSET:
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} already carries the purchasing decision "
                    f"'{demand.get_purchasing_state_display()}'. Clear or cancel "
                    "the purchasing side before changing the part."
                ),
            )

        if demand.purchased_qty:
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} already has {demand.purchased_qty} on "
                    "order. Remove its purchase-order allocations first."
                ),
            )

        if demand.issued_qty or demand.issuance_state != IssuanceState.NOT_ISSUED:
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} has already been issued against — "
                    "the part that physically moved cannot be rewritten."
                ),
            )

        link = (
            PurchaseOrderDemandLink.objects.filter(
                part_demand_id=demand.pk, deleted_at__isnull=True
            )
            .select_related("purchase_order_line__purchase_order")
            .first()
        )
        if link is not None:
            po = link.purchase_order_line.purchase_order
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} is allocated to {po.po_number} line "
                    f"{link.purchase_order_line.line_number}. De-link it from that "
                    "order before changing the part."
                ),
            )

        # The graph check is the backstop for anything the specific checks above
        # miss: if this demand is alone in its graph, no other member can
        # disagree about the part, and recalculate() re-derives cleanly.
        if demand.graph_id is not None and not cls._is_sole_graph_member(demand):
            return SubstitutionVerdict(
                allowed=False,
                reason=(
                    f"Demand #{demand.pk} shares a fulfillment graph with other "
                    "records, which must all agree on one part. Split it out "
                    "before changing the part."
                ),
            )

        return SubstitutionVerdict(allowed=True)

    @staticmethod
    def _is_sole_graph_member(demand: PartDemand) -> bool:
        from app.procurement.models import PurchaseOrderLine, ShipmentLine

        demand_peers = (
            PartDemand.objects.filter(
                graph_id=demand.graph_id, deleted_at__isnull=True
            )
            .exclude(pk=demand.pk)
            .exists()
        )
        if demand_peers:
            return False
        for model in (PurchaseOrderLine, ShipmentLine):
            if model.objects.filter(
                graph_id=demand.graph_id, deleted_at__isnull=True
            ).exists():
                return False
        return True
