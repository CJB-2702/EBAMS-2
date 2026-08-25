"""The inward seam surface (D12). Backs PartDemandContext.record_issuance().

This is where the sanctioned convention break lives, and it is worth being
blunt about the cost: record_issuance takes the net quantity AS AN ARGUMENT. It
does not, and cannot, query PartIssue to compute it — procurement holds no FK
into inventory and may not import it. If anything ever creates a PartIssue row
without going through inventory.PartIssuanceOrchestrator, issued_qty drifts and
nothing in this app can detect it. The orchestrator is the only supported write
path.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.managers.part_demand_quantity_manager import (
    PartDemandQuantityManager,
)
from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import DemandDimension


class PartDemandIssuanceManager:
    @classmethod
    def record(
        cls,
        *,
        demand,
        net_issued_qty: Decimal,
        to_stage: str,
        actor=None,
        issued_to=None,
        notes: str = "",
        commit: bool = True,
    ):
        """Apply the net issued quantity and move issuance_state.

        to_stage is supplied by the caller, never computed. issuance_state
        NEVER auto-flips from comparing issued_qty to anything (D30, D36): a
        demand can reach Issued at 4 units against 10 purchased, because the
        job only needed 4. Whoever handles the material closes it out
        explicitly. purchased_qty, issued_qty, and every accepted shipment
        quantity are informational inputs to that judgment, never a gate on it.

        THIS IS THE ONLY WRITER OF `PartDemand.issued_to`, and it is LAST
        TAKER WINS — the column is a current-state snapshot answering "who has
        it", not a log. When a demand is issued across several sessions the
        column names the most recent recipient and the journal row written
        below carries the full history.
        """
        PartDemandQuantityManager.apply_issued_qty(
            demand=demand,
            net_issued_qty=net_issued_qty,
            actor=actor,
            commit=commit,
        )
        # Saved unconditionally, exactly as apply_issued_qty above saves
        # issued_qty regardless of `commit` — `commit` gates the state
        # transition's journal row, not the snapshot columns. Every caller runs
        # inside the orchestrator's transaction, so this rolls back with it.
        if issued_to is not None and demand.issued_to_id != issued_to.pk:
            demand.issued_to = issued_to
            demand.save(update_fields=["issued_to", "updated_at"])
        # A handover ALWAYS earns its journal row, including the second and
        # third partial one against a demand already sitting in Partially
        # Issued. Without this the state machine's same-stage refusal made
        # repeat partial issuance impossible: the receipt committed its stock
        # movements and then blew up on "Already in that state."
        return PartDemandStateManager.transition(
            demand=demand,
            dimension=DemandDimension.ISSUANCE,
            to_stage=to_stage,
            allow_same_stage=True,
            actor=actor,
            notes=notes
            or PartDemandNarrator.issuance_recorded(net_issued_qty=net_issued_qty),
            commit=commit,
        )
