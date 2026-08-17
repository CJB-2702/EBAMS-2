"""Manager: reconciliation task generation and resolution
(`overages_shortages_and_reconciliation.md` §2, FD-9's parent+child grain).

Auto Intake never touches this path (FD-13: ACTIVE -> CLOSED directly,
partial receipts resolved by `ShipmentLineManager.split_line` instead). This
manager exists for the scan-engine session flow (Phase 5) and is exercised
here only through `IntakeContext.transition_to_reconciliation`/`resolve_line`
so the verbs and grain are proven ahead of that build.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.models.intake.enums import (
    AllocationCondition,
    ReconciliationResolutionType,
    ReconciliationStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.inventory.models.intake.part_reconciliation_line import PartReconciliationLine
from app.inventory.models.intake.part_reconciliation_session import (
    PartReconciliationSession,
)


class ReconciliationManager:
    @classmethod
    def generate_tasks(
        cls, *, intake_session: IntakeSession, actor=None
    ) -> list[PartReconciliationSession]:
        """One `PartReconciliationSession` per part with a discrepant
        shipment line, each carrying a `PartReconciliationLine` child per
        discrepant line — never netted across shipment lines (FD-9)."""
        linked_shipment_ids = list(
            intake_session.shipment_associations.filter(
                deleted_at__isnull=True
            ).values_list("shipment_id", flat=True)
        )
        if not linked_shipment_ids:
            return []

        from app.procurement.models import ShipmentLine

        shipment_lines = list(
            ShipmentLine.objects.filter(
                shipment_id__in=linked_shipment_ids, deleted_at__isnull=True
            ).select_related("part")
        )

        by_part: dict[int, list[PartReconciliationLine]] = {}
        for line in shipment_lines:
            totals = ItemAllocation.objects.filter(
                intake_session=intake_session,
                shipment_line=line,
                deleted_at__isnull=True,
            ).aggregate(
                good=Sum("quantity", filter=Q(condition=AllocationCondition.GOOD)),
                rejected=Sum("quantity", filter=Q(condition=AllocationCondition.REJECTED)),
            )
            allocated = totals["good"] or Decimal("0")
            rejected = totals["rejected"] or Decimal("0")
            if allocated + rejected == line.quantity:
                continue  # exactly satisfied — no discrepancy

            by_part.setdefault(line.part_id, []).append(
                (line, allocated, rejected)
            )

        created: list[PartReconciliationSession] = []
        with transaction.atomic():
            for part_id, entries in by_part.items():
                total_expected = sum((e[0].quantity for e in entries), Decimal("0"))
                total_allocated = sum((e[1] for e in entries), Decimal("0"))
                total_rejected = sum((e[2] for e in entries), Decimal("0"))

                reconciliation, _ = PartReconciliationSession.objects.get_or_create(
                    intake_session=intake_session,
                    part_id=part_id,
                    defaults={
                        "status": ReconciliationStatus.PENDING,
                        "total_expected_quantity": total_expected,
                        "total_allocated_quantity": total_allocated,
                        "total_rejected_quantity": total_rejected,
                        "created_by": actor,
                        "updated_by": actor,
                    },
                )
                for line, allocated, rejected in entries:
                    PartReconciliationLine.objects.get_or_create(
                        part_reconciliation_session=reconciliation,
                        shipment_line=line,
                        defaults={
                            "expected_quantity": line.quantity,
                            "allocated_quantity": allocated,
                            "rejected_quantity": rejected,
                            "resolution_type": ReconciliationResolutionType.NONE,
                            "created_by": actor,
                            "updated_by": actor,
                        },
                    )
                created.append(reconciliation)
        return created

    @classmethod
    def apply_resolution(
        cls,
        *,
        line: PartReconciliationLine,
        resolution_type: str,
        notes: str = "",
        actor=None,
    ) -> PartReconciliationLine:
        """Resolve one child line. The parent auto-resolves the moment every
        child under it carries a real resolution_type."""
        if resolution_type == ReconciliationResolutionType.NONE:
            raise InventoryValidationError(
                ["A reconciliation line must be resolved with a real resolution type."]
            )

        with transaction.atomic():
            line.resolution_type = resolution_type
            line.notes = notes
            line.updated_by = actor
            line.save(
                update_fields=["resolution_type", "notes", "updated_by", "updated_at"]
            )

            if line.rejected_quantity > 0:
                cls._propagate_rejection_note(line=line, actor=actor)

            parent = line.part_reconciliation_session
            unresolved = parent.lines.filter(
                deleted_at__isnull=True, resolution_type=ReconciliationResolutionType.NONE
            ).exists()
            if not unresolved and parent.status != ReconciliationStatus.RESOLVED:
                parent.status = ReconciliationStatus.RESOLVED
                parent.resolved_by = actor
                parent.resolved_at = timezone.now()
                parent.updated_by = actor
                parent.save(
                    update_fields=[
                        "status",
                        "resolved_by",
                        "resolved_at",
                        "updated_by",
                        "updated_at",
                    ]
                )
        return line

    @classmethod
    def _propagate_rejection_note(cls, *, line: PartReconciliationLine, actor=None) -> None:
        """The phase file's brief ("rejected-quantity propagation into
        `rejection_notes` on accept") names a column that doesn't exist here
        — `PartReconciliationLine` carries `notes`, not a separate
        `rejection_notes` field (FD-9's child grain; no schema change this
        phase). `ShipmentLine.rejection_notes` DOES exist, but it is the
        write seam `IntakeCommitOrchestrator._settle_shipment_line` ->
        `ShipmentContext.accept_line` owns exclusively together with
        `quantity_accepted` (see the Phase 4 acceptance-seam test) — writing
        it here, before close, would race that seam. So the propagation
        target is `ShipmentLine.comments`, the same JSONField audit-trail
        mechanism `IntakeContext.pull_external_allocation` already uses.
        """
        shipment_line = line.shipment_line
        entries = list(shipment_line.comments.get("reconciliation_notes", []))
        entries.append(
            {
                "note": (
                    f"Part reconciliation resolved as '{line.resolution_type}': "
                    f"{line.rejected_quantity} rejected of {line.expected_quantity} "
                    f"expected. {line.notes}".strip()
                ),
                "at": timezone.now().isoformat(),
                "by": actor.pk if actor is not None else None,
            }
        )
        shipment_line.comments["reconciliation_notes"] = entries
        shipment_line.updated_by = actor
        shipment_line.save(update_fields=["comments", "updated_by", "updated_at"])

    # ------------------------------------------------------------------ #
    # Reassignment
    # ------------------------------------------------------------------ #

    @classmethod
    def reassign_allocation(
        cls,
        *,
        allocation: ItemAllocation,
        target_shipment_line=None,
        actor=None,
    ) -> ItemAllocation:
        """The reassignment widget (`overages_and_shortages_guide.md` §4):
        update `ItemAllocation.shipment_line_id` in place — no other side
        effects. Per-line reconciliation totals (`total_*_quantity` on
        `PartReconciliationSession`) are computed fresh by `generate_tasks`
        each time it runs rather than kept live-denormalized anywhere, so
        there is nothing else here to recompute."""
        if target_shipment_line is not None:
            linked_shipment_ids = set(
                allocation.intake_session.shipment_associations.filter(
                    deleted_at__isnull=True
                ).values_list("shipment_id", flat=True)
            )
            if target_shipment_line.shipment_id not in linked_shipment_ids:
                raise InventoryValidationError(
                    [
                        "The target shipment line is not associated with this "
                        "allocation's session."
                    ]
                )

        with transaction.atomic():
            allocation.shipment_line = target_shipment_line
            allocation.updated_by = actor
            allocation.save(
                update_fields=["shipment_line", "updated_by", "updated_at"]
            )

            session = allocation.intake_session
            has_unlinked = ItemAllocation.objects.filter(
                intake_session=session, deleted_at__isnull=True, shipment_line__isnull=True
            ).exists()
            if session.has_unlinked_allocations != has_unlinked:
                session.has_unlinked_allocations = has_unlinked
                session.updated_by = actor
                session.save(
                    update_fields=["has_unlinked_allocations", "updated_by", "updated_at"]
                )
        return allocation
