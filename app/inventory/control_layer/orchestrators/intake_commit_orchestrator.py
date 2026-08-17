"""Orchestrator: the intake <-> procurement <-> stock write coordinator.

Mirrors `PartIssuanceOrchestrator`'s role — the one place a write workflow
legitimately crosses the inventory/procurement boundary. `IntakeCommitOrchestrator.close`
is the ONLY path that ever calls `ShipmentContext.accept_line` (FD-6) or
injects stock via `StockLedgerManager.inject` on session close:

    IntakeCommitOrchestrator.close(session_id, actor)
      |- validate reconciliation barrier (no PENDING PartReconciliationSession)
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
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from app.inventory.control_layer.errors import ReconciliationBarrierError
from app.inventory.control_layer.factories.warehouse_factory import WarehouseFactory
from app.inventory.control_layer.guards.intake_guard import IntakeSessionStateMachine
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionStatus,
    ReconciliationStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.inventory.models.intake.part_reconciliation_session import (
    PartReconciliationSession,
)


class IntakeCommitOrchestrator:
    @classmethod
    def close(cls, *, session_id: int, actor=None, notes: str = "") -> IntakeSession:
        session = IntakeSession.objects.select_related("warehouse", "room").get(
            pk=session_id
        )
        IntakeSessionStateMachine.check(
            from_status=session.status, to_status=IntakeSessionStatus.CLOSED
        )

        cls._check_reconciliation_barrier(session=session)

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

            has_unlinked = ItemAllocation.objects.filter(
                intake_session=session, deleted_at__isnull=True, shipment_line__isnull=True
            ).exists()

            session.status = IntakeSessionStatus.CLOSED
            session.closed_at = timezone.now()
            session.has_unlinked_allocations = has_unlinked
            if notes:
                session.notes = f"{session.notes}\n{notes}".strip()
            session.updated_by = actor
            session.save(
                update_fields=[
                    "status",
                    "closed_at",
                    "has_unlinked_allocations",
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )

        return session

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _check_reconciliation_barrier(*, session: IntakeSession) -> None:
        pending_part_ids = list(
            PartReconciliationSession.objects.filter(
                intake_session=session,
                status=ReconciliationStatus.PENDING,
                deleted_at__isnull=True,
            ).values_list("part_id", flat=True)
        )
        if pending_part_ids:
            raise ReconciliationBarrierError(
                session_id=session.pk, pending_part_ids=pending_part_ids
            )

    @classmethod
    def _settle_shipment_line(
        cls, *, session: IntakeSession, shipment_line_id: int, session_allocations, actor=None
    ) -> None:
        from app.procurement.control_layer.shipment_context import ShipmentContext
        from app.procurement.models import ShipmentLine

        line = ShipmentLine.objects.select_related("shipment", "part").get(
            pk=shipment_line_id
        )

        # Every CLOSED session's allocations for this line, PLUS this
        # session's own (which is not yet marked CLOSED in the DB — the
        # save() above hasn't run for this transaction). That is the
        # cumulative-total semantics FD-6/FD-10 call for.
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
