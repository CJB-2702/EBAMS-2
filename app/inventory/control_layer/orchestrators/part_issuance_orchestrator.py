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
from django.utils import timezone

from app.administration.models import User
from app.inventory.control_layer.guards.issuance_guard import IssuanceValidator
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.models import (
    ActiveInventory,
    IssueSessionStatus,
    IssueType,
    PartIssue,
    PartIssueSession,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import IssuanceState


class PartIssuanceOrchestrator:
    @classmethod
    def issue(
        cls,
        *,
        quantity: Decimal,
        issue_type: str = IssueType.FOR_PART_DEMAND,
        demand_id: int | None = None,
        issued_to=None,
        issued_to_asset_id: int | None = None,
        active_inventory_id: int | None = None,
        session: PartIssueSession | None = None,
        to_stage: str = IssuanceState.ISSUED,
        actor=None,
        notes: str = "",
        issued_at=None,
    ) -> PartIssue:
        """Hand material to a person, an asset, or (still, by default) a
        demand — Phase 6 (FD-5) extends the original demand-only seam with
        stock provenance and the two direct-issue types.

        to_stage is supplied by the CALLER, never computed from quantities
        (D30, D36), and is only meaningful when `demand_id` is set — direct
        issues never touch a demand's axes. A demand can reach Issued at 4
        units against 10 purchased, because the job only needed 4:

          Issued                        normal terminal case, no return expected
          Partially Issued              some but not the full expected amount
          Issued Pending Reconciliation material expected to come back

        `active_inventory_id`, when given, withdraws (positive quantity) or
        re-injects (negative quantity, i.e. a return) stock through
        `StockLedgerManager` in the same transaction, and snapshots
        `unit_cost_at_issue`/`serial_number` off that balance row.
        """
        if quantity == 0:
            raise ValueError("An issuance quantity cannot be zero.")
        IssuanceValidator.check_recipient_shape(
            issue_type=issue_type,
            demand_id=demand_id,
            issued_to_id=getattr(issued_to, "pk", issued_to),
            issued_to_asset_id=issued_to_asset_id,
        )
        # `can_issue_parts` is checked by whichever presentation-layer portal
        # owns this workflow (StockPolicy's two-tier convention), not here —
        # this seam is also the seed scripts' direct write path and must not
        # require a permission grant just to construct dev fixtures.

        with transaction.atomic():
            active_inventory = None
            serial = ""
            unit_cost_at_issue = None
            if active_inventory_id is not None:
                active_inventory = ActiveInventory.objects.select_related(
                    "warehouse", "room", "storage_location", "part"
                ).get(pk=active_inventory_id)
                serial = active_inventory.serial_number
                unit_cost_at_issue = active_inventory.unit_cost_avg

                if quantity > 0:
                    StockLedgerManager.withdraw(
                        room=active_inventory.room,
                        storage_location=active_inventory.storage_location,
                        part=active_inventory.part,
                        qty=quantity,
                        serial=serial,
                        actor=actor,
                    )
                else:
                    StockLedgerManager.inject(
                        warehouse=active_inventory.warehouse,
                        room=active_inventory.room,
                        storage_location=active_inventory.storage_location,
                        part=active_inventory.part,
                        qty=abs(quantity),
                        serial=serial,
                        unit_cost=unit_cost_at_issue,
                        actor=actor,
                    )

            issue = PartIssue.objects.create(
                session=session,
                issue_type=issue_type,
                part_demand_id=demand_id,
                issued_to=issued_to,
                issued_to_asset_id=issued_to_asset_id,
                from_room=active_inventory.room if active_inventory else None,
                from_storage_location=active_inventory.storage_location if active_inventory else None,
                serial_number=serial,
                unit_cost_at_issue=unit_cost_at_issue,
                quantity=quantity,
                notes=notes,
                **({"issued_at": issued_at} if issued_at is not None else {}),
                created_by=actor,
                updated_by=actor,
            )

            if demand_id is not None:
                net = cls.net_issued_for_demand(demand_id=demand_id)
                PartDemandContext(demand_id).record_issuance(
                    net_issued_qty=net,
                    to_stage=to_stage,
                    actor=actor,
                    commit=False,
                )

        return issue

    @classmethod
    def commit_session(
        cls,
        *,
        lines: list[dict],
        issued_by,
        issued_to=None,
        issued_to_asset_id: int | None = None,
        issue_type: str = IssueType.FOR_PART_DEMAND,
        issue_reason: str = "",
        notes: str = "",
        issued_at=None,
    ) -> PartIssueSession:
        """Commit an entire active issuance session (staged draft queue) in a single
        atomic database transaction.

        Creates a PartIssueSession header record, then iterates over each staged line item
        to generate corresponding PartIssue rows, withdraw stock balances, and update
        associated PartDemand issuance states.
        """
        if not lines:
            raise ValueError("Cannot commit an empty issuance session.")

        import uuid

        with transaction.atomic():
            session_number = (
                f"ISS-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )
            session = PartIssueSession.objects.create(
                session_number=session_number,
                issue_type=issue_type,
                status=IssueSessionStatus.COMMITTED,
                issued_by=issued_by,
                issued_to=issued_to,
                issued_to_asset_id=issued_to_asset_id,
                issue_reason=issue_reason,
                notes=notes,
                **({"issued_at": issued_at} if issued_at is not None else {}),
                created_by=issued_by,
                updated_by=issued_by,
            )

            for line in lines:
                line_qty = Decimal(str(line["quantity"]))
                line_issue_type = line.get("issue_type", issue_type)
                line_demand_id = line.get("demand_id")
                line_issued_to = (
                    User.objects.get(pk=line["issued_to_id"])
                    if line.get("issued_to_id")
                    else issued_to
                )
                line_issued_to_asset_id = (
                    line.get("issued_to_asset_id") or issued_to_asset_id
                )
                line_active_inventory_id = line.get("active_inventory_id")
                line_notes = line.get("notes", "")

                cls.issue(
                    session=session,
                    quantity=line_qty,
                    issue_type=line_issue_type,
                    demand_id=line_demand_id,
                    issued_to=line_issued_to,
                    issued_to_asset_id=line_issued_to_asset_id,
                    active_inventory_id=line_active_inventory_id,
                    to_stage=IssuanceState.ISSUED,
                    actor=issued_by,
                    notes=line_notes,
                    issued_at=issued_at,
                )

        return session

    @classmethod
    def record_return(
        cls,
        *,
        quantity: Decimal,
        issue_type: str = IssueType.FOR_PART_DEMAND,
        demand_id: int | None = None,
        issued_to=None,
        issued_to_asset_id: int | None = None,
        active_inventory_id: int | None = None,
        to_stage: str = IssuanceState.ISSUED,
        actor=None,
        notes: str = "",
    ) -> PartIssue:
        """Record material coming back: a negative row against the same
        recipient. Defaults to resolving the demand back to Issued with
        issued_qty netted down — the close-out is a human decision, so the
        caller may pass a different to_stage. When `active_inventory_id` is
        given, the returned quantity is re-injected into that balance row."""
        return cls.issue(
            quantity=-abs(quantity),
            issue_type=issue_type,
            demand_id=demand_id,
            issued_to=issued_to,
            issued_to_asset_id=issued_to_asset_id,
            active_inventory_id=active_inventory_id,
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
