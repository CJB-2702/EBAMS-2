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

from app.inventory.control_layer.factories.issue_session_number_factory import (
    IssueSessionNumberFactory,
)
from app.inventory.control_layer.guards.issuance_guard import IssuanceValidator
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.models import (
    ActiveInventory,
    IssueReason,
    IssueType,
    PartIssue,
    PartIssueSession,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import IssuanceState, PartDemand


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
        sync_demand: bool = True,
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

        `sync_demand=False` writes the PartIssue row and moves stock but
        leaves the demand's issued_qty and axis alone — used ONLY by
        `commit_session`, which writes every line for a demand and then syncs
        that demand once. Any other caller passing it would reintroduce
        exactly the silent drift this seam exists to prevent.

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

            if demand_id is not None and sync_demand:
                cls._sync_demand(
                    demand_id=demand_id,
                    to_stage=to_stage,
                    actor=actor,
                    issued_to=issued_to,
                )

        return issue

    # ------------------------------------------------------------------ #
    # The demand seam, split out so a session can write every line for a
    # demand FIRST and then move that demand's axis exactly once.
    # ------------------------------------------------------------------ #

    @classmethod
    def _sync_demand(
        cls,
        *,
        demand_id: int,
        to_stage: str,
        actor=None,
        issued_to=None,
        journal_note: str = "",
        net: Decimal | None = None,
    ) -> Decimal:
        """Push the demand's net issued quantity and axis into procurement.

        MUST be called inside a transaction the caller already opened —
        `commit=False` is passed through for exactly that reason.

        Called ONCE PER DEMAND, not once per line. A receipt that draws the
        same demand from two bins (the container ran dry mid-handover) would
        otherwise write two journal rows and briefly park the demand in
        Partially Issued on its way to Issued, which is a lie about what
        happened: one handover, one entry.
        """
        if net is None:
            net = cls.net_issued_for_demand(demand_id=demand_id)
        PartDemandContext(demand_id).record_issuance(
            net_issued_qty=net,
            to_stage=to_stage,
            actor=actor,
            issued_to=issued_to,
            notes=journal_note,
            commit=False,
        )
        return net

    @staticmethod
    def resolve_issuance_stage(*, net_issued: Decimal, quantity_requested: Decimal) -> str:
        """Which issuance stage a demand lands on given what is now out.

        This is the portal supplying `to_stage`, NOT the demand auto-flipping
        from its own quantities — D30/D36 forbid procurement inferring the
        axis, and it still does not. The judgment is made here, by the caller,
        and handed over.

        Deliberately generous at the top end: issuing MORE than was asked for
        still lands on Issued. Over-issue is a warning the portal raises before
        submission, not a different state afterwards.
        """
        if net_issued <= 0:
            return IssuanceState.NOT_ISSUED
        if net_issued >= quantity_requested:
            return IssuanceState.ISSUED
        return IssuanceState.PARTIALLY_ISSUED

    @classmethod
    def commit_session(
        cls,
        *,
        lines: list[dict],
        issued_by,
        issued_to,
        issue_reason: str = IssueReason.OTHER,
        issue_reason_detail: str = "",
        notes: str = "",
        issued_at=None,
    ) -> PartIssueSession:
        """Commit a whole receipt — one handover, to one person, atomically.

        ONE RECIPIENT. `issued_to` is required and is stamped onto every line,
        so a line can no longer carry a recipient that disagrees with the
        receipt it sits on. The previous shape took a per-line `issued_to_id`
        that silently beat the header's value, which made the portal's
        recipient dropdown decorative.

        A DEMAND MAY APPEAR ON SEVERAL LINES. Two bins for one demand is the
        ordinary case when a container runs dry mid-handover, and serialised
        parts always split — three serials is three lines of one unit each,
        because `ActiveInventory` holds one row per serial. So the lines are
        written first and each distinct demand is synced once afterwards, with
        its stage resolved from the resulting net.
        """
        if not lines:
            raise ValueError("Cannot commit an empty issuance session.")
        if issued_to is None:
            raise ValueError("An issuance session must name who received the material.")

        with transaction.atomic():
            session = PartIssueSession.objects.create(
                session_number=IssueSessionNumberFactory.next_number(issued_at=issued_at),
                issued_by=issued_by,
                issued_to=issued_to,
                issue_reason=issue_reason or IssueReason.OTHER,
                issue_reason_detail=issue_reason_detail,
                notes=notes,
                **({"issued_at": issued_at} if issued_at is not None else {}),
                created_by=issued_by,
                updated_by=issued_by,
            )

            # Pass 1 — every line becomes a PartIssue row and moves stock. The
            # demands are deliberately left untouched here.
            quantity_by_demand: dict[int, Decimal] = {}
            for line in lines:
                line_qty = Decimal(str(line["quantity"]))
                line_demand_id = line.get("demand_id")

                cls.issue(
                    session=session,
                    quantity=line_qty,
                    issue_type=line.get("issue_type", IssueType.FOR_PART_DEMAND),
                    demand_id=line_demand_id,
                    issued_to=issued_to,
                    # Line grain, not header grain: the header is one person,
                    # but the "Issue from Location" portal can point a single
                    # grabbed line at an asset instead. The header lost its
                    # `issued_to_asset` for exactly this reason — an asset is a
                    # property of what was taken, not of who signed for it.
                    issued_to_asset_id=line.get("issued_to_asset_id"),
                    active_inventory_id=line.get("active_inventory_id"),
                    actor=issued_by,
                    notes=line.get("notes", ""),
                    issued_at=issued_at,
                    sync_demand=False,
                )
                if line_demand_id is not None:
                    quantity_by_demand[line_demand_id] = (
                        quantity_by_demand.get(line_demand_id, Decimal("0")) + line_qty
                    )

            # Pass 2 — one axis move and one journal row per demand.
            if quantity_by_demand:
                requested_by_demand = dict(
                    PartDemand.objects.filter(pk__in=quantity_by_demand)
                    .values_list("pk", "quantity_requested")
                )
                recipient_label = (
                    issued_to.get_full_name() or issued_to.username
                    if hasattr(issued_to, "username")
                    else str(issued_to)
                )
                for demand_id, handed_over in quantity_by_demand.items():
                    net = cls.net_issued_for_demand(demand_id=demand_id)
                    stage = cls.resolve_issuance_stage(
                        net_issued=net,
                        quantity_requested=requested_by_demand.get(
                            demand_id, Decimal("0")
                        ),
                    )
                    cls._sync_demand(
                        demand_id=demand_id,
                        to_stage=stage,
                        actor=issued_by,
                        net=net,
                        issued_to=issued_to,
                        journal_note=PartDemandNarrator.issuance_handover(
                            quantity=handed_over,
                            recipient_label=recipient_label,
                            session_number=session.session_number,
                            net_issued_qty=net,
                        ),
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
