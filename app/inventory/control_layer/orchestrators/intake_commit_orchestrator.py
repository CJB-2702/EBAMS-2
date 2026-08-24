"""Orchestrator: the intake <-> procurement <-> stock write coordinator.

Mirrors `PartIssuanceOrchestrator`'s role — the one place a write workflow
legitimately crosses the inventory/procurement boundary. `IntakeCommitOrchestrator.close`
is the ONLY path that ever calls `ShipmentContext.accept_line` (FD-6) or
injects stock via `StockLedgerManager.inject` on session close:

    IntakeCommitOrchestrator.post_stock(session_id, actor)
      |- group this session's live allocations by shipment_line
      |- for each shipment_line:
      |     cumulative_good = sum(GOOD qty across every CLOSED session + this one)
      |     ShipmentContext(line.shipment_id).accept_line(cumulative_good)   <- FD-6
      |     cumulative_received = cumulative_good + cumulative_rejected
      |     if cumulative_received < line.quantity:
      |         ShipmentContext(line.shipment_id).split_line(cumulative_received)  <- FD-27
      |     inject each of THIS session's own GOOD allocations into stock
      |- inject this session's unmanifested (shipment_line=NULL) GOOD allocations too
      |- session.status = CLOSED

Both sides run in ONE transaction, opened here. `quantity_accepted` is never
written anywhere else in `app/inventory` — see the acceptance grep in the
Phase 4 build plan.

THIS IS THE STOCK-POSTING ACT (intake_portal_workflow.md §4.3): irreversible,
all-or-nothing, and stamped on `IntakeSession.stock_posted_at/_by`. There is
no partial posting of clean lines while disputed lines wait — once stock
merges into the general pool it loses its per-receipt traceability anyway, so
splitting the act would multiply the state space for no recoverable benefit.

It deliberately does NOT stamp `recording_locked_at`. Recording and stock
posting are INDEPENDENT AXES (§4.2): recording locks only when a user
explicitly says so, and `IntakeContext.lock_recording` is the verb that does
it. The end-of-recording fork calls both in sequence for option 1 and only
the lock for option 2 — it is two calls, not a mode flag, precisely so
neither can become a side effect of the other.

The old reconciliation barrier is gone with the reconciliation tables (§7.1):
there is nothing to sign off, so there is nothing to block on. A short
receipt posts exactly like a clean one — the warehouse needs the parts
pickable today, and the buyer's argument with the vendor is a separate
timeline (§4.1).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from app.inventory.control_layer.errors import StockAlreadyPosted
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.guards.intake_guard import IntakeSessionStateMachine
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.narrators.intake_narrator import IntakeNarrator
from app.inventory.models.intake.enums import AllocationCondition, IntakeSessionStatus
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation


class IntakeCommitOrchestrator:
    @classmethod
    def post_stock(cls, *, session_id: int, actor=None, notes: str = "") -> IntakeSession:
        session = IntakeSession.objects.select_related("warehouse", "room").get(
            pk=session_id
        )
        if session.stock_posted_at is not None:
            raise StockAlreadyPosted(session_id=session.pk)
        IntakeSessionStateMachine.check(
            from_status=session.status, to_status=IntakeSessionStatus.CLOSED
        )

        with transaction.atomic():
            allocations = list(
                ItemAllocation.objects.filter(
                    intake_session=session, deleted_at__isnull=True
                ).select_related("shipment_line", "shipment_line__shipment", "part")
            )

            manifested = [a for a in allocations if a.shipment_line_id is not None]
            unmanifested = [a for a in allocations if a.shipment_line_id is None]

            shipment_line_ids = {a.shipment_line_id for a in manifested}
            for shipment_line_id in shipment_line_ids:
                cls._settle_shipment_line(
                    session=session,
                    shipment_line_id=shipment_line_id,
                    session_allocations=[
                        a for a in manifested if a.shipment_line_id == shipment_line_id
                    ],
                    actor=actor,
                )

            target_room = session.room or WarehouseFactory.intake_room(
                warehouse=session.warehouse
            )
            for allocation in unmanifested:
                if allocation.condition != AllocationCondition.GOOD:
                    continue
                StockLedgerManager.inject(
                    warehouse=session.warehouse,
                    room=target_room,
                    storage_location=None,
                    part=allocation.part,
                    qty=allocation.quantity,
                    serial=allocation.serial_number,
                    actor=actor,
                )

            session.status = IntakeSessionStatus.CLOSED
            session.stock_posted_at = timezone.now()
            session.stock_posted_by = actor
            if notes:
                session.notes = f"{session.notes}\n{notes}".strip()
            session.updated_by = actor
            session.save(
                update_fields=[
                    "status",
                    "stock_posted_at",
                    "stock_posted_by",
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )

            cls._narrate(session=session, allocations=allocations, actor=actor)

        return session

    @classmethod
    def close(cls, *, session_id: int, actor=None, notes: str = "") -> IntakeSession:
        """Alias for post_stock for backward compatibility."""
        return cls.post_stock(session_id=session_id, actor=actor, notes=notes)

    @staticmethod
    def _narrate(*, session, allocations, actor=None) -> None:
        """The irreversible act belongs on the session's own thread (§8), not
        only in a flash message that vanishes on the next click."""
        from app.inventory.control_layer.session_thread import session_thread

        good = sum(
            (a.quantity for a in allocations if a.condition == AllocationCondition.GOOD),
            Decimal("0"),
        )
        rejected = sum(
            (
                a.quantity
                for a in allocations
                if a.condition != AllocationCondition.GOOD
            ),
            Decimal("0"),
        )
        session_thread(session, actor).add_comment(
            IntakeNarrator.stock_posted(good_qty=good, rejected_qty=rejected),
            is_human_made=False,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @classmethod
    def _settle_shipment_line(
        cls, *, session: IntakeSession, shipment_line_id: int, session_allocations, actor=None
    ) -> None:
        from app.procurement.control_layer.shipment_context import ShipmentContext
        from app.procurement.models import ShipmentLine

        line = ShipmentLine.objects.select_related("shipment", "part").get(
            pk=shipment_line_id
        )

        # THE SHIPMENT LINE IS THE UNIT OF TRUTH. THE SESSION IS A LENS
        # ONTO IT (§5.5). Every CLOSED session's allocations for this line,
        # PLUS this session's own (not yet marked CLOSED in the DB — the
        # save() above hasn't run for this transaction). Scoping this sum to
        # one session would be a bug: it is what manufactures phantom
        # shortages when two sessions receive against the same line.
        closed_or_this_session = Q(intake_session__status=IntakeSessionStatus.CLOSED) | Q(
            intake_session=session
        )
        totals = ItemAllocation.objects.filter(
            closed_or_this_session,
            shipment_line_id=shipment_line_id,
            deleted_at__isnull=True,
        ).aggregate(
            good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
            rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
        )
        cumulative_good = totals["good"] or Decimal("0")
        cumulative_rejected = totals["rejected"] or Decimal("0")
        cumulative_received = cumulative_good + cumulative_rejected

        context = ShipmentContext(line.shipment_id)
        context.accept_line(line=line, quantity_accepted=cumulative_good, actor=actor)

        if cumulative_received < line.quantity:
            context.split_line(line=line, received_qty=cumulative_received, actor=actor)

        target_room = session.room or WarehouseFactory.intake_room(
            warehouse=session.warehouse
        )
        for allocation in session_allocations:
            if allocation.condition != AllocationCondition.GOOD:
                continue
            StockLedgerManager.inject(
                warehouse=session.warehouse,
                room=target_room,
                storage_location=None,
                part=allocation.part,
                qty=allocation.quantity,
                serial=allocation.serial_number,
                actor=actor,
            )
