"""Manager: the Auto Intake portal's math and pseudo-session creation
(`auto_intake_workflow_guide.md` §3, FD-13).

`existing_balances` / `compute_delta` are the pure math (worked examples A-C
are the literal test spec). `commit` is the one write entrypoint: it creates
the `IntakeSession` (`intake_method='manual_package'`), the delta
`ItemAllocation` rows, then hands off to `IntakeCommitOrchestrator` to close
the session in the same transaction — the portal is always a single atomic
receive, never a draft left open.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.intake_guard import AutoIntakeValidator
from app.inventory.models.intake.enums import (
    AllocationCondition,
    AllocationIntakeMethod,
    IntakeSessionMethod,
    IntakeSessionStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.intake_session_shipment_link import (
    IntakeSessionShipmentLink,
)
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.procurement.models import ShipmentLine


class AutoIntakeManager:
    # ------------------------------------------------------------------ #
    # Pure math
    # ------------------------------------------------------------------ #

    @classmethod
    def existing_balances(cls, *, shipment_line_id: int) -> tuple[Decimal, Decimal]:
        """(A_existing, R_existing) — the sum of every live allocation's
        quantity against this shipment line, split by condition."""
        totals = ItemAllocation.objects.filter(
            shipment_line_id=shipment_line_id, deleted_at__isnull=True
        ).aggregate(
            good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
            rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
        )
        return (
            totals["good"] or Decimal("0"),
            totals["rejected"] or Decimal("0"),
        )

    @classmethod
    def compute_delta(
        cls,
        *,
        shipment_line: ShipmentLine,
        accepted_target: Decimal,
        rejected_target: Decimal,
    ) -> dict:
        """Validate floors/cap, then compute the incremental delta for one
        line (§3.3). Returns existing balances alongside the deltas so the
        UI can render both."""
        existing_good, existing_rejected = cls.existing_balances(
            shipment_line_id=shipment_line.pk
        )
        AutoIntakeValidator.check_line_targets(
            accepted_user=accepted_target,
            rejected_user=rejected_target,
            accepted_existing=existing_good,
            rejected_existing=existing_rejected,
            shipped_qty=shipment_line.quantity,
        )
        return {
            "shipment_line_id": shipment_line.pk,
            "existing_good": existing_good,
            "existing_rejected": existing_rejected,
            "delta_good": accepted_target - existing_good,
            "delta_rejected": rejected_target - existing_rejected,
        }

    # ------------------------------------------------------------------ #
    # Write path
    # ------------------------------------------------------------------ #

    @classmethod
    def commit(
        cls,
        *,
        operator,
        warehouse_id: int,
        room_id: int | None,
        shipment_id: int,
        line_targets: dict[int, tuple[Decimal, Decimal]],
        hardware_device_id: str = "",
        actor=None,
    ) -> IntakeSession:
        """One atomic receive: build the pseudo-session, materialize every
        line's delta as `ItemAllocation` rows, link the shipment, then close
        through `IntakeCommitOrchestrator`.

        `line_targets` maps `shipment_line_id -> (accepted_target,
        rejected_target)` — every line comes pre-validated by
        `compute_delta`, but the cap/floor check is re-run here inside the
        transaction so a stale read never slips a violation through.
        """
        from app.inventory.control_layer.orchestrators.intake_commit_orchestrator import (
            IntakeCommitOrchestrator,
        )

        if not line_targets:
            raise InventoryValidationError(
                ["At least one shipment line must have a target quantity."]
            )

        lines = {
            line.pk: line
            for line in ShipmentLine.objects.filter(
                pk__in=line_targets.keys(), deleted_at__isnull=True
            ).select_related("part", "shipment")
        }
        missing = set(line_targets.keys()) - set(lines.keys())
        if missing:
            raise InventoryValidationError(
                [f"Shipment line(s) {sorted(missing)} not found."]
            )

        deltas = {
            line_id: cls.compute_delta(
                shipment_line=lines[line_id],
                accepted_target=accepted,
                rejected_target=rejected,
            )
            for line_id, (accepted, rejected) in line_targets.items()
        }

        with transaction.atomic():
            session = IntakeSession.objects.create(
                operator=operator,
                warehouse_id=warehouse_id,
                room_id=room_id,
                status=IntakeSessionStatus.ACTIVE,
                intake_method=IntakeSessionMethod.MANUAL_PACKAGE,
                hardware_device_id=hardware_device_id,
                created_by=actor,
                updated_by=actor,
            )
            IntakeSessionShipmentLink.objects.create(
                intake_session=session,
                shipment_id=shipment_id,
                created_by=actor,
                updated_by=actor,
            )

            for line_id, delta in deltas.items():
                line = lines[line_id]
                if delta["delta_good"] > 0:
                    ItemAllocation.objects.create(
                        intake_session=session,
                        shipment_line=line,
                        part=line.part,
                        quantity=delta["delta_good"],
                        condition=AllocationCondition.GOOD,
                        intake_method=AllocationIntakeMethod.MANUAL,
                        created_by=actor,
                        updated_by=actor,
                    )
                if delta["delta_rejected"] > 0:
                    ItemAllocation.objects.create(
                        intake_session=session,
                        shipment_line=line,
                        part=line.part,
                        quantity=delta["delta_rejected"],
                        condition=AllocationCondition.REJECTED,
                        intake_method=AllocationIntakeMethod.MANUAL,
                        created_by=actor,
                        updated_by=actor,
                    )

            return IntakeCommitOrchestrator.close(session_id=session.pk, actor=actor)
