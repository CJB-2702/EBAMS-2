"""Handler: the D43 auto-complete rollup.

Runs after EVERY write to purchasing_state or issuance_state — never on
shipment_state or demand_state. Transitions demand_state -> Completed when both
hold:

  - purchasing_state has progressed past unset and past Denied (at least
    Approved), and
  - issuance_state has reached Issued.

Whichever condition is satisfied second is what fires it.

WHY shipment_state IS EXCLUDED. This looks wrong until you look at how the
queue is actually worked. A Requester marks their material received and expects
the demand to read as done, full stop. Shipment/stocking tracking is a
decoupled background process — high volume, ideally fed by an external system
rather than typed in (D16's motivating case). Blocking Completed on an axis
nobody in the completion path touches would leave every finished demand looking
unfinished. So a demand can be Completed while shipment_state sits at Shipped.
That is correct. This supersedes D9a's "all three other axes must be terminal".
"""

from __future__ import annotations

from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandDimension,
    DemandState,
    IssuanceState,
    PurchasingState,
)

#: Axes whose movement can satisfy the rollup. A write to any other axis is not
#: even checked.
TRIGGERING_DIMENSIONS = frozenset(
    {DemandDimension.PURCHASING, DemandDimension.ISSUANCE}
)

#: purchasing_state values that mean money has NOT been cleared to move.
NON_CLEARED_PURCHASING_STATES = frozenset(
    {PURCHASING_STATE_UNSET, PurchasingState.DENIED}
)


class DemandCompletionHandler:
    @classmethod
    def check(cls, *, demand, dimension: str, actor=None) -> bool:
        """Returns True if this call completed the demand."""
        if dimension not in TRIGGERING_DIMENSIONS:
            return False
        if demand.demand_state != DemandState.APPROVED:
            # Already Completed, or Cancelled/Rejected — nothing to roll up.
            return False
        if demand.purchasing_state in NON_CLEARED_PURCHASING_STATES:
            return False
        if demand.issuance_state != IssuanceState.ISSUED:
            return False

        # Imported here rather than at module scope: the manager calls this
        # handler, so a module-level import would be circular. This is the one
        # recursion, and it terminates — the transition below is on
        # demand_state, which is not a triggering dimension.
        from app.procurement.control_layer.managers.part_demand_state_manager import (
            PartDemandStateManager,
        )

        PartDemandStateManager.transition(
            demand=demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.COMPLETED,
            actor=None,  # derived — no human decided this
            notes=PartDemandNarrator.auto_completed(),
            is_system_generated=True,
            raise_on_refusal=False,
            commit=False,
        )
        return True
