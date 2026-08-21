"""Factory: stateless creation of the PartDemand hub row and its four
initializing journal rows."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
)
from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandPriority,
    DemandSourceModule,
    DemandState,
    IssuanceState,
    PartDemand,
    ShipmentState,
)


class PartDemandFactory:
    @classmethod
    def create(
        cls,
        *,
        part_id: int,
        domain_id: int,
        quantity_requested: Decimal,
        demand_state: str = DemandState.REQUIRED,
        priority: str = DemandPriority.MEDIUM,
        needed_by=None,
        notes: str = "",
        expected_cost: Decimal | None = None,
        source: str | None = None,
        source_module: str | None = None,
        event_id: int | None = None,
        serial_number_tracking_required: bool = False,
        requested_by=None,
        actor=None,
        commit: bool = True,
    ) -> PartDemand:
        """Create the hub row and nothing else.

        THE CALLER OWNS DOMAIN ASSIGNMENT. Every PartDemand requires exactly
        one domain, mandatory (D5) — it identifies who is meant to receive the
        part. It is derived from the requester's own domain assignment, never
        chosen from a dropdown (except in the one case where a requester holds
        more than one). A demand created with the wrong domain is invisible to
        the people meant to fulfill it, and fails quietly rather than loudly.

        THE CALLER OWNS ITS OWN LINK ROW. This factory does not create link
        rows, does not know what a link row is, and never will (G3, D7). A
        future Maintenance or Dispatching app calling this must create its own
        table's row pointing at the returned demand's id.

        demand_state defaults to Required — a human filling in a form is asking
        for something now. Projected is only for a caller explicitly forecasting
        future work; there is no UI path to it.
        """
        resolved_source = source or source_module or DemandSourceModule.PROCUREMENT

        def _create() -> PartDemand:
            demand = PartDemand.objects.create(
                part_id=part_id,
                domain_id=domain_id,
                quantity_requested=quantity_requested,
                priority=priority,
                needed_by=needed_by,
                notes=notes,
                expected_cost=expected_cost,
                source=resolved_source,
                event_id=event_id,
                serial_number_tracking_required=serial_number_tracking_required,
                requested_by=requested_by,
                # The four axes open at their defaults. No guard runs at
                # create: there is no illegal opening state to defend against.
                demand_state=demand_state,
                purchasing_state=PURCHASING_STATE_UNSET,
                shipment_state=ShipmentState.REQUEST_NOT_SENT,
                issuance_state=IssuanceState.NOT_ISSUED,
                created_by=actor,
                updated_by=actor,
            )
            PartDemandStateManager.initialize(
                demand=demand, actor=actor, commit=False
            )
            # D82 node-init: a demand created directly (no link yet) gets its
            # own fresh single-member graph in the same transaction as its
            # own creation. A caller that immediately links this demand (a
            # wizard step) still goes through this path first, then folds the
            # single-member graph into the other side's via
            # PurchaseOrderDemandLinkManager.allocate()'s merge.
            GraphSummaryManager.initialize_node(entity=demand, actor=actor)
            return demand

        if commit:
            with transaction.atomic():
                return _create()
        return _create()
