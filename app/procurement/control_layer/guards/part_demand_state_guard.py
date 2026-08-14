"""Guard type: StateMachine. Legal-transition dicts per axis, plus the three
cross-dimension gates (D9-D11), failing open per D13.

THIS IS NOT A RULES ENGINE AND MUST NOT GROW INTO ONE. The dicts below exist
so the legal-transition shape is visible in one glanceable place (D23), not as
the seed of a generalized mechanism. The per-organization templated version was
considered and deferred whole to tech debt (D21) — see
docs/procurement/tech_debt/20260808 process template workflow engine.md.

Transitions are unrestricted by default *within* what the dicts allow; the only
cross-axis rules are the three gates. There are no others.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandDimension,
    DemandState,
    IssuanceState,
    PurchasingState,
    PurchaseOrderStatus,
    ShipmentState,
)

# --------------------------------------------------------------------------- #
# Legal transitions, one dict per axis (D23)
# --------------------------------------------------------------------------- #

DEMAND_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    DemandState.PROJECTED: frozenset(
        {DemandState.REQUIRED, DemandState.CANCELLED}
    ),
    DemandState.REQUIRED: frozenset(
        {DemandState.APPROVED, DemandState.REJECTED, DemandState.CANCELLED}
    ),
    # Rejected loops back to Required on resubmission — same row, no reopen
    # action, no versioning (M5). The journal carries the full loop.
    DemandState.REJECTED: frozenset({DemandState.REQUIRED, DemandState.CANCELLED}),
    DemandState.APPROVED: frozenset(
        {DemandState.CANCELLED, DemandState.COMPLETED}
    ),
    DemandState.CANCELLED: frozenset(),
    DemandState.COMPLETED: frozenset(),
}

PURCHASING_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    PURCHASING_STATE_UNSET: frozenset(
        {PurchasingState.APPROVED, PurchasingState.DENIED, PurchasingState.PURCHASED}
    ),
    PurchasingState.APPROVED: frozenset(
        {PurchasingState.PURCHASED, PurchasingState.CANCELLED, PURCHASING_STATE_UNSET}
    ),
    PurchasingState.DENIED: frozenset({PURCHASING_STATE_UNSET}),
    # Purchased -> unset is THE ONE BACKWARD MOVE in this axis, and it exists
    # solely for D56: cancelling a PO line removes its demand links and returns
    # those demands to "no purchasing decision has been made", which is
    # accurate once the thing that was going to buy them is gone.
    PurchasingState.PURCHASED: frozenset(
        {PurchasingState.CANCELLED, PURCHASING_STATE_UNSET}
    ),
    PurchasingState.CANCELLED: frozenset({PURCHASING_STATE_UNSET}),
}

SHIPMENT_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    ShipmentState.REQUEST_NOT_SENT: frozenset(
        {ShipmentState.REQUEST_RECEIVED_BY_VENDOR}
    ),
    ShipmentState.REQUEST_RECEIVED_BY_VENDOR: frozenset(
        {ShipmentState.PRODUCTION_IN_PROGRESS, ShipmentState.VENDOR_PREPARED_TO_SHIP}
    ),
    ShipmentState.PRODUCTION_IN_PROGRESS: frozenset(
        {ShipmentState.VENDOR_PREPARED_TO_SHIP}
    ),
    ShipmentState.VENDOR_PREPARED_TO_SHIP: frozenset({ShipmentState.SHIPPED}),
    ShipmentState.SHIPPED: frozenset(
        {
            ShipmentState.BACKORDERED,
            ShipmentState.LOST,
            ShipmentState.DELIVERED_TO_DEPOT,
            ShipmentState.DELIVERED_TO_LOCAL,
        }
    ),
    # Backordered items ship in pieces; a backorder re-enters the chain.
    ShipmentState.BACKORDERED: frozenset(
        {ShipmentState.VENDOR_PREPARED_TO_SHIP, ShipmentState.SHIPPED}
    ),
    ShipmentState.LOST: frozenset({ShipmentState.SHIPPED}),
    ShipmentState.DELIVERED_TO_DEPOT: frozenset({ShipmentState.DELIVERED_TO_LOCAL}),
    # DELIVERED_TO_LOCAL is this kit's owned terminal stage (D35). IN_STOCK
    # belongs to the later Inventory build and nothing here writes it.
    ShipmentState.DELIVERED_TO_LOCAL: frozenset({ShipmentState.IN_STOCK}),
    ShipmentState.IN_STOCK: frozenset(),
}

ISSUANCE_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    IssuanceState.NOT_ISSUED: frozenset(
        {
            IssuanceState.PARTIALLY_ISSUED,
            IssuanceState.ISSUED,
            IssuanceState.ISSUED_PENDING_RECONCILIATION,
            IssuanceState.ISSUED_RECONCILIATION_REQUIRED,
        }
    ),
    IssuanceState.PARTIALLY_ISSUED: frozenset(
        {
            IssuanceState.ISSUED,
            IssuanceState.ISSUED_PENDING_RECONCILIATION,
            IssuanceState.ISSUED_RECONCILIATION_REQUIRED,
            IssuanceState.NOT_ISSUED,
        }
    ),
    # Issued <-> Pending Reconciliation is the borrow/return loop. The
    # mechanics of who decides and when belong to the later Inventory build;
    # the surface is legal here so that build has something to target.
    IssuanceState.ISSUED: frozenset(
        {
            IssuanceState.ISSUED_PENDING_RECONCILIATION,
            IssuanceState.PARTIALLY_ISSUED,
            # D77/D78: the backwards Issued -> Reconciliation Required move —
            # a physical hand-off already happened and the books haven't
            # caught up, discovered after the row was already marked Issued.
            IssuanceState.ISSUED_RECONCILIATION_REQUIRED,
        }
    ),
    IssuanceState.ISSUED_PENDING_RECONCILIATION: frozenset(
        {IssuanceState.ISSUED, IssuanceState.PARTIALLY_ISSUED}
    ),
    # Resolved once the inventory system's books catch up to reality.
    IssuanceState.ISSUED_RECONCILIATION_REQUIRED: frozenset(
        {IssuanceState.ISSUED, IssuanceState.PARTIALLY_ISSUED}
    ),
}

TRANSITIONS_BY_DIMENSION: dict[str, dict[str, frozenset[str]]] = {
    DemandDimension.DEMAND: DEMAND_STATE_TRANSITIONS,
    DemandDimension.PURCHASING: PURCHASING_STATE_TRANSITIONS,
    DemandDimension.SHIPMENT: SHIPMENT_STATE_TRANSITIONS,
    DemandDimension.ISSUANCE: ISSUANCE_STATE_TRANSITIONS,
}

#: purchasing_state values that mean a linked PO is still live, for Gate 2.
ACTIVE_PURCHASING_STATES = frozenset(
    {PurchasingState.APPROVED, PurchasingState.PURCHASED}
)

#: PurchaseOrder.status values that mean the order itself is still live.
LIVE_PURCHASE_ORDER_STATUSES = frozenset(
    {
        PurchaseOrderStatus.DRAFT,
        PurchaseOrderStatus.PLACED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
    }
)


@dataclass(frozen=True)
class TransitionVerdict:
    """The outcome of a legality check.

    ``allowed`` False is a hard refusal with a reason naming the next action.
    ``flagged`` True is D13's fail-open: the guard could not decide, so the
    transition goes through and PartDemandUpdate.flagged_for_review is set.
    """

    allowed: bool
    reason: str = ""
    flagged: bool = False


class PartDemandTransitionStateMachine:
    """Checks one axis transition against its dict and the three gates."""

    @classmethod
    def check(
        cls,
        *,
        demand,
        dimension: str,
        from_stage: str,
        to_stage: str,
    ) -> TransitionVerdict:
        transitions = TRANSITIONS_BY_DIMENSION.get(dimension)
        if transitions is None:
            # Undecidable: an axis the guard does not know about. Fail open.
            return TransitionVerdict(
                allowed=True,
                reason=f"Unknown dimension '{dimension}' — allowed and flagged.",
                flagged=True,
            )

        if from_stage == to_stage:
            return TransitionVerdict(allowed=False, reason="Already in that state.")

        legal = transitions.get(from_stage)
        if legal is None:
            # The current stored value is not a key in the dict — the row is in
            # a state this guard cannot reason about. Fail open (D13) rather
            # than trapping the demand.
            return TransitionVerdict(
                allowed=True,
                reason=(
                    f"Current stage '{from_stage}' is not a known {dimension} stage — "
                    f"allowed and flagged."
                ),
                flagged=True,
            )

        if to_stage not in legal:
            return TransitionVerdict(
                allowed=False,
                reason=(
                    f"{dimension}: '{from_stage}' cannot move to '{to_stage}'."
                ),
            )

        return cls._check_gates(
            demand=demand, dimension=dimension, to_stage=to_stage
        )

    # ------------------------------------------------------------------ #
    # The complete gate set. Three gates. There are no others.
    # ------------------------------------------------------------------ #

    @classmethod
    def _check_gates(cls, *, demand, dimension: str, to_stage: str) -> TransitionVerdict:
        if dimension == DemandDimension.PURCHASING:
            return cls._gate_one_purchasing_requires_approval(
                demand=demand, to_stage=to_stage
            )
        if dimension == DemandDimension.DEMAND and to_stage == DemandState.CANCELLED:
            return cls._gate_two_cancel_requires_dead_purchase_orders(demand=demand)
        # Gate 3 (D11): issuance_state is gated on NOTHING. Issuing from stock
        # on hand with no PO ever cut is legal at any time, from any purchasing
        # or shipment state. Its absence here is the gate.
        return TransitionVerdict(allowed=True)

    @staticmethod
    def _gate_one_purchasing_requires_approval(
        *, demand, to_stage: str
    ) -> TransitionVerdict:
        """Gate 1 (D9). purchasing_state cannot leave unset until demand_state
        reaches Approved — an unapproved demand cannot be purchased against.

        In practice Approved is usually reached as a side effect of a Buyer's
        link (D42), not as a separate human step waited on. This gate is what
        the Buyer's opt-out checkbox re-arms.
        """
        # Returning TO unset is the D56 line-cancellation path — never gated.
        if to_stage == PURCHASING_STATE_UNSET:
            return TransitionVerdict(allowed=True)

        if demand.demand_state == DemandState.APPROVED:
            return TransitionVerdict(allowed=True)
        # Completed demands have necessarily passed through Approved.
        if demand.demand_state == DemandState.COMPLETED:
            return TransitionVerdict(allowed=True)

        return TransitionVerdict(
            allowed=False,
            reason=(
                f"Demand #{demand.pk} is '{demand.demand_state}' and must be approved "
                f"before its purchasing state can move."
            ),
        )

    @staticmethod
    def _gate_two_cancel_requires_dead_purchase_orders(*, demand) -> TransitionVerdict:
        """Gate 2 (D10). demand_state cannot reach Cancelled while a linked PO
        is still active.

        Cancelling the order before cancelling the request behind it is how
        real purchasing works. The refusal names the PO that must be cancelled
        first — the message is doing the work, so make the next action obvious.
        """
        if demand.purchasing_state not in ACTIVE_PURCHASING_STATES:
            return TransitionVerdict(allowed=True)

        blocking = (
            demand.allocations.filter(
                is_active=True,
                deleted_at__isnull=True,
                purchase_order_line__deleted_at__isnull=True,
                purchase_order_line__purchase_order__status__in=(
                    LIVE_PURCHASE_ORDER_STATUSES
                ),
                purchase_order_line__purchase_order__deleted_at__isnull=True,
            )
            .select_related("purchase_order_line__purchase_order")
            .first()
        )
        if blocking is None:
            return TransitionVerdict(allowed=True)

        po = blocking.purchase_order_line.purchase_order
        return TransitionVerdict(
            allowed=False,
            reason=(
                f"Purchase order {po.po_number} is still active. Cancel it before "
                f"cancelling demand #{demand.pk}."
            ),
        )
