"""Orchestrator: THE cross-app write coordinator.

This is the only class in either app carrying the Orchestrator suffix, which is
correct — it is the one place a *write* workflow legitimately crosses an app
boundary. Shipment classes call into procurement too, but they live in
procurement now, so there is no crossing at all.

    PartIssuanceOrchestrator.issue(demand_id, issued_to, quantity, actor)
      |- INSERT inventory.PartIssue(quantity=+N or -N)
      |- net = sum(PartIssue.quantity for this demand)     <- computed HERE
      '- procurement.PartDemandContext.record_issuance(
             net_issued_qty=net, to_stage=..., actor=actor, commit=False)
           |- PartDemandQuantityManager sets issued_qty = net
           |- PartDemandStateManager.transition(issuance, to_stage, ...)
           '- DemandCompletionHandler.check()   -> may auto-complete (D43)

Both sides run in ONE transaction, opened here.

THE DIRECTION IS THE WHOLE POINT. inventory imports procurement freely;
procurement never imports inventory, holds no FK into it, and cannot compute
the net itself. If a PartIssue row is ever created outside this call,
issued_qty drifts and nothing in procurement can detect it. This is the only
supported write path.

A RETURN IS A SECOND, NEGATIVE ROW against the same demand (D39) — not a return
table, not a quantity_returned column, not a boolean. issued_qty is always the
net: issue 10 then return all 10 and it rests at 0, which is valid, not an
error. The legacy hub had was_borrow_and_return and quantity_returned columns
that were never populated in practice; that is the evidence this shape is right.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from app.inventory.models import PartIssue
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import IssuanceState


class PartIssuanceOrchestrator:
    @classmethod
    def issue(
        cls,
        *,
        demand_id: int,
        issued_to,
        quantity: Decimal,
        to_stage: str = IssuanceState.ISSUED,
        actor=None,
        notes: str = "",
        issued_at=None,
    ) -> PartIssue:
        """Hand material to a person against a demand.

        to_stage is supplied by the CALLER, never computed from quantities
        (D30, D36). A demand can reach Issued at 4 units against 10 purchased,
        because the job only needed 4. Whoever handles the material closes it
        out explicitly:

          Issued                        normal terminal case, no return expected
          Partially Issued              some but not the full expected amount
          Issued Pending Reconciliation material expected to come back
        """
        if quantity == 0:
            raise ValueError("An issuance quantity cannot be zero.")

        with transaction.atomic():
            issue = PartIssue.objects.create(
                part_demand_id=demand_id,
                issued_to=issued_to,
                quantity=quantity,
                notes=notes,
                **({"issued_at": issued_at} if issued_at is not None else {}),
                created_by=actor,
                updated_by=actor,
            )

            net = cls.net_issued_for_demand(demand_id=demand_id)

            PartDemandContext(demand_id).record_issuance(
                net_issued_qty=net,
                to_stage=to_stage,
                actor=actor,
                commit=False,
            )

        return issue

    @classmethod
    def record_return(
        cls,
        *,
        demand_id: int,
        issued_to,
        quantity: Decimal,
        to_stage: str = IssuanceState.ISSUED,
        actor=None,
        notes: str = "",
    ) -> PartIssue:
        """Record material coming back: a negative row against the same demand.

        Defaults to resolving the demand back to Issued with issued_qty netted
        down — the close-out is a human decision, so the caller may pass a
        different to_stage.
        """
        return cls.issue(
            demand_id=demand_id,
            issued_to=issued_to,
            quantity=-abs(quantity),
            to_stage=to_stage,
            actor=actor,
            notes=notes,
        )

    @staticmethod
    def net_issued_for_demand(*, demand_id: int) -> Decimal:
        """The net of every signed issue row for this demand. Computed in
        inventory, because this is where the rows live."""
        return PartIssue.objects.filter(
            part_demand_id=demand_id, deleted_at__isnull=True
        ).aggregate(net=Sum("quantity"))["net"] or Decimal("0")
