"""Context: the single public entrypoint for intake control logic.

Every intake-session write goes through here — callers use domain verbs
(`start_session`, `close_session`, ...) rather than reaching for the
managers/guards directly. Mirrors `TopographyContext`'s shape.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.intake_guard import (
    AllocationValidator,
    IntakePolicy,
    IntakeSessionStateMachine,
)
from app.inventory.control_layer.managers.auto_intake_manager import AutoIntakeManager
from app.inventory.control_layer.managers.intake_matching_manager import (
    IntakeMatchingManager,
)
from app.inventory.control_layer.managers.reconciliation_manager import (
    ReconciliationManager,
)
from app.inventory.control_layer.orchestrators.intake_commit_orchestrator import (
    IntakeCommitOrchestrator,
)
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
from app.inventory.models.intake.part_reconciliation_line import PartReconciliationLine


class IntakeContext:
    def __init__(self, intake_session_id: int) -> None:
        self.intake_session_id = intake_session_id
        self._session: IntakeSession | None = None

    @property
    def session(self) -> IntakeSession:
        if self._session is None:
            self._session = IntakeSession.objects.select_related(
                "warehouse", "room", "operator"
            ).get(pk=self.intake_session_id)
        return self._session

    # ------------------------------------------------------------------ #
    # Root creation
    # ------------------------------------------------------------------ #

    @classmethod
    def start_session(
        cls,
        *,
        operator,
        warehouse_id: int,
        room_id: int | None = None,
        intake_method: str = IntakeSessionMethod.SCAN,
        hardware_device_id: str = "",
        actor=None,
    ) -> "IntakeContext":
        session = IntakeSession.objects.create(
            operator=operator,
            warehouse_id=warehouse_id,
            room_id=room_id,
            status=IntakeSessionStatus.DRAFT,
            intake_method=intake_method,
            hardware_device_id=hardware_device_id,
            created_by=actor,
            updated_by=actor,
        )
        return cls(session.pk)

    # ------------------------------------------------------------------ #
    # Shipment linkage
    # ------------------------------------------------------------------ #

    def associate_shipment(self, *, shipment_id: int, actor=None) -> IntakeSessionShipmentLink:
        from app.procurement.models import Shipment

        shipment = Shipment.objects.get(pk=shipment_id)
        IntakePolicy.check_shipment_domain_access(actor=actor, shipment=shipment)

        link, _ = IntakeSessionShipmentLink.objects.get_or_create(
            intake_session=self.session,
            shipment=shipment,
            defaults={"created_by": actor, "updated_by": actor},
        )
        if self.session.status == IntakeSessionStatus.DRAFT:
            self.session.status = IntakeSessionStatus.ACTIVE
            self.session.updated_by = actor
            self.session.save(update_fields=["status", "updated_by", "updated_at"])
        return link

    # ------------------------------------------------------------------ #
    # Manual allocations (scan-engine-adjacent; Auto Intake uses its own
    # manager path via commit_auto_intake)
    # ------------------------------------------------------------------ #

    def create_manual_allocation(
        self,
        *,
        shipment_line_id: int | None,
        part_id: int,
        quantity: Decimal,
        serial_number: str = "",
        condition: str = AllocationCondition.GOOD,
        actor=None,
    ) -> ItemAllocation:
        AllocationValidator.check_quantity_positive(quantity=quantity)
        AllocationValidator.check_serial_implies_unit_qty(
            serial_number=serial_number, quantity=quantity
        )
        AllocationValidator.check_composite_sn_unique(
            part_id=part_id, serial_number=serial_number
        )

        with transaction.atomic():
            allocation = ItemAllocation.objects.create(
                intake_session=self.session,
                shipment_line_id=shipment_line_id,
                part_id=part_id,
                quantity=quantity,
                serial_number=serial_number,
                composite_sn=f"{part_id}:{serial_number}" if serial_number else "",
                condition=condition,
                intake_method=AllocationIntakeMethod.MANUAL,
                created_by=actor,
                updated_by=actor,
            )
            if shipment_line_id is None and not self.session.has_unlinked_allocations:
                self.session.has_unlinked_allocations = True
                self.session.updated_by = actor
                self.session.save(
                    update_fields=["has_unlinked_allocations", "updated_by", "updated_at"]
                )
        return allocation

    def split_allocation(
        self,
        *,
        allocation_id: int,
        good_qty: Decimal,
        rejected_qty: Decimal,
        actor=None,
    ) -> list[ItemAllocation]:
        """Split one allocation row into good/rejected siblings — used when
        a scan-engine operator inspects a staged batch after the fact."""
        allocation = ItemAllocation.objects.get(
            pk=allocation_id, intake_session=self.session
        )
        if good_qty + rejected_qty != allocation.quantity:
            raise InventoryValidationError(
                [
                    f"Split quantities ({good_qty} + {rejected_qty}) must equal "
                    f"the original allocation's quantity ({allocation.quantity})."
                ]
            )

        with transaction.atomic():
            allocation.deleted_at = timezone.now()
            allocation.updated_by = actor
            allocation.save(update_fields=["deleted_at", "updated_by", "updated_at"])

            new_rows = []
            if good_qty > 0:
                new_rows.append(
                    ItemAllocation.objects.create(
                        intake_session=self.session,
                        shipment_line_id=allocation.shipment_line_id,
                        part_id=allocation.part_id,
                        quantity=good_qty,
                        serial_number=allocation.serial_number,
                        composite_sn=allocation.composite_sn,
                        condition=AllocationCondition.GOOD,
                        intake_method=allocation.intake_method,
                        created_by=actor,
                        updated_by=actor,
                    )
                )
            if rejected_qty > 0:
                new_rows.append(
                    ItemAllocation.objects.create(
                        intake_session=self.session,
                        shipment_line_id=allocation.shipment_line_id,
                        part_id=allocation.part_id,
                        quantity=rejected_qty,
                        serial_number="",
                        composite_sn="",
                        condition=AllocationCondition.REJECTED,
                        intake_method=allocation.intake_method,
                        created_by=actor,
                        updated_by=actor,
                    )
                )
        return new_rows

    # ------------------------------------------------------------------ #
    # Scan engine (Phase 5)
    # ------------------------------------------------------------------ #

    def process_scan(
        self,
        *,
        raw_payload: str,
        condition: str = AllocationCondition.GOOD,
        actor=None,
    ) -> ItemAllocation:
        """The scan entrypoint verb: parse the barcode, resolve the part,
        validate serial uniqueness, size the quantity off `Part.qty_per_scan`
        / `Part.sn_expected`, resolve (or stage) the target shipment line,
        create the allocation, then run the FIFO cascade for that part.

        A parse failure raises `BarcodeParseError` (an `InventoryValidationError`
        subtype) rather than crashing — the presentation layer is expected to
        catch it and fall back to manual entry via `create_manual_allocation`.
        """
        from app.parts.models import Part

        sku, serial_number = IntakeMatchingManager.parse_barcode(raw_payload)

        try:
            part = Part.objects.get(part_number=sku)
        except Part.DoesNotExist:
            raise InventoryValidationError([f"No part found for SKU '{sku}'."])

        IntakeMatchingManager.validate_serial_uniqueness(
            part_id=part.pk, serial_number=serial_number, session_id=self.intake_session_id
        )

        quantity = Decimal("1") if part.sn_expected else part.qty_per_scan
        AllocationValidator.check_quantity_positive(quantity=quantity)
        AllocationValidator.check_serial_implies_unit_qty(
            serial_number=serial_number, quantity=quantity
        )

        target_line = IntakeMatchingManager.find_target_line(session=self.session, part=part)

        with transaction.atomic():
            allocation = ItemAllocation.objects.create(
                intake_session=self.session,
                shipment_line=target_line,
                part=part,
                quantity=quantity,
                serial_number=serial_number,
                composite_sn=f"{part.pk}:{serial_number}" if serial_number else "",
                condition=condition,
                intake_method=AllocationIntakeMethod.SCAN,
                created_by=actor,
                updated_by=actor,
            )

            IntakeMatchingManager.execute_fifo_cascade(session=self.session, part=part)

            has_unlinked = ItemAllocation.objects.filter(
                intake_session=self.session, deleted_at__isnull=True, shipment_line__isnull=True
            ).exists()
            if self.session.has_unlinked_allocations != has_unlinked:
                self.session.has_unlinked_allocations = has_unlinked
                self.session.updated_by = actor
                self.session.save(
                    update_fields=["has_unlinked_allocations", "updated_by", "updated_at"]
                )

        allocation.refresh_from_db()
        return allocation

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    def transition_to_reconciliation(self, *, actor=None) -> list:
        session = self.session
        IntakeSessionStateMachine.check(
            from_status=session.status, to_status=IntakeSessionStatus.RECONCILING
        )
        with transaction.atomic():
            tasks = ReconciliationManager.generate_tasks(
                intake_session=session, actor=actor
            )
            session.status = IntakeSessionStatus.RECONCILING
            session.updated_by = actor
            session.save(update_fields=["status", "updated_by", "updated_at"])
        return tasks

    def resolve_line(
        self,
        *,
        reconciliation_line_id: int,
        resolution_type: str,
        notes: str = "",
        actor=None,
    ) -> PartReconciliationLine:
        line = PartReconciliationLine.objects.select_related(
            "part_reconciliation_session"
        ).get(pk=reconciliation_line_id, part_reconciliation_session__intake_session=self.session)
        return ReconciliationManager.apply_resolution(
            line=line, resolution_type=resolution_type, notes=notes, actor=actor
        )

    def reassign_allocation(
        self,
        *,
        allocation_id: int,
        target_shipment_line_id: int | None = None,
        actor=None,
    ) -> ItemAllocation:
        """The reassignment widget (`overages_and_shortages_guide.md` §4):
        move one allocation of THIS session to a different shipment line
        also associated with this session, or to
        `target_shipment_line_id=None` for unassociated/quarantine."""
        allocation = ItemAllocation.objects.get(pk=allocation_id, intake_session=self.session)
        # Point the allocation's cached FK at this Context's own `session`
        # instance (rather than whatever `select_related` would fetch fresh)
        # so the manager's write below lands on the same object this
        # Context keeps cached — `self.session` stays consistent afterward
        # without a forced reload.
        allocation.intake_session = self.session

        target_line = None
        if target_shipment_line_id is not None:
            from app.procurement.models import ShipmentLine

            target_line = ShipmentLine.objects.select_related("shipment").get(
                pk=target_shipment_line_id
            )
        return ReconciliationManager.reassign_allocation(
            allocation=allocation, target_shipment_line=target_line, actor=actor
        )

    def pull_external_allocation(
        self, *, allocation_id: int, target_line_id: int, actor=None
    ) -> ItemAllocation:
        """FD-26: move an excess/unlinked `ItemAllocation` from ANOTHER
        session into THIS session's shortage line (`overages_and_shortages_guide.md`
        §5). Validates the source allocation is currently unlinked and
        belongs to a different session, and that the target line belongs to
        a shipment associated with this session; then re-parents the
        allocation and appends an audit note to the target `ShipmentLine`'s
        `comments` (a `JSONField` — no schema change needed, FD-28)."""
        from app.procurement.models import ShipmentLine

        allocation = ItemAllocation.objects.select_related("intake_session").get(
            pk=allocation_id
        )
        if allocation.shipment_line_id is not None:
            raise InventoryValidationError(
                ["Only an unlinked (excess/unmanifested) allocation can be pulled in."]
            )
        if allocation.intake_session_id == self.session.pk:
            raise InventoryValidationError(
                ["That allocation already belongs to this session."]
            )

        target_line = ShipmentLine.objects.select_related("shipment").get(pk=target_line_id)
        linked_shipment_ids = set(
            self.session.shipment_associations.filter(deleted_at__isnull=True).values_list(
                "shipment_id", flat=True
            )
        )
        if target_line.shipment_id not in linked_shipment_ids:
            raise InventoryValidationError(
                ["The target shipment line is not associated with this session."]
            )

        with transaction.atomic():
            source_session_id = allocation.intake_session_id

            allocation.intake_session = self.session
            allocation.shipment_line = target_line
            allocation.updated_by = actor
            allocation.save(
                update_fields=["intake_session", "shipment_line", "updated_by", "updated_at"]
            )

            note_entries = list(target_line.comments.get("intake_notes", []))
            note_entries.append(
                {
                    "note": (
                        f"Overage allocation #{allocation.pk} pulled from external "
                        f"session #{source_session_id} into this session "
                        f"(#{self.session.pk})."
                    ),
                    "at": timezone.now().isoformat(),
                    "by": actor.pk if actor is not None else None,
                }
            )
            target_line.comments["intake_notes"] = note_entries
            target_line.updated_by = actor
            target_line.save(update_fields=["comments", "updated_by", "updated_at"])

            IntakeSession.objects.filter(pk=source_session_id).update(
                has_unlinked_allocations=ItemAllocation.objects.filter(
                    intake_session_id=source_session_id,
                    deleted_at__isnull=True,
                    shipment_line__isnull=True,
                ).exists()
            )
            has_unlinked_here = ItemAllocation.objects.filter(
                intake_session=self.session, deleted_at__isnull=True, shipment_line__isnull=True
            ).exists()
            if self.session.has_unlinked_allocations != has_unlinked_here:
                self.session.has_unlinked_allocations = has_unlinked_here
                self.session.updated_by = actor
                self.session.save(
                    update_fields=["has_unlinked_allocations", "updated_by", "updated_at"]
                )

        allocation.refresh_from_db()
        return allocation

    # ------------------------------------------------------------------ #
    # Auto Intake portal (FD-13)
    # ------------------------------------------------------------------ #

    @classmethod
    def commit_auto_intake(
        cls,
        *,
        operator,
        warehouse_id: int,
        room_id: int | None,
        shipment_id: int,
        line_targets: dict[int, tuple[Decimal, Decimal]],
        hardware_device_id: str = "",
        actor=None,
    ) -> "IntakeContext":
        """The Auto Intake portal's single write: build the pseudo-session,
        materialize deltas, and close in one transaction."""
        IntakePolicy.check_permission(actor=actor)
        session = AutoIntakeManager.commit(
            operator=operator,
            warehouse_id=warehouse_id,
            room_id=room_id,
            shipment_id=shipment_id,
            line_targets=line_targets,
            hardware_device_id=hardware_device_id,
            actor=actor,
        )
        return cls(session.pk)

    # ------------------------------------------------------------------ #
    # Close / cancel
    # ------------------------------------------------------------------ #

    def close_session(self, *, actor=None, notes: str = "") -> IntakeSession:
        self._session = IntakeCommitOrchestrator.close(
            session_id=self.intake_session_id, actor=actor, notes=notes
        )
        return self._session

    def cancel_session(self, *, actor=None, reason: str = "") -> IntakeSession:
        """Soft-delete sweep across every child row (§5.4): allocations,
        shipment links, and reconciliation parent+child rows all retract
        together so nothing survives the session as a live orphan."""
        session = self.session
        IntakeSessionStateMachine.check(
            from_status=session.status, to_status=IntakeSessionStatus.CANCELLED
        )
        now = timezone.now()
        with transaction.atomic():
            ItemAllocation.objects.filter(
                intake_session=session, deleted_at__isnull=True
            ).update(deleted_at=now, updated_by=actor, updated_at=now)
            IntakeSessionShipmentLink.objects.filter(
                intake_session=session, deleted_at__isnull=True
            ).update(deleted_at=now, updated_by=actor, updated_at=now)
            PartReconciliationLine.objects.filter(
                part_reconciliation_session__intake_session=session,
                deleted_at__isnull=True,
            ).update(deleted_at=now, updated_by=actor, updated_at=now)
            session.reconciliations.filter(deleted_at__isnull=True).update(
                deleted_at=now, updated_by=actor, updated_at=now
            )

            session.status = IntakeSessionStatus.CANCELLED
            session.notes = f"{session.notes}\nCancelled: {reason}".strip() if reason else session.notes
            session.updated_by = actor
            session.save(update_fields=["status", "notes", "updated_by", "updated_at"])
        self._session = session
        return session
