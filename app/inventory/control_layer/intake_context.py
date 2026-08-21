"""Context: the single public entrypoint for intake control logic.

Every intake-session write goes through here — callers use domain verbs
(`start_session`, `close_session`, ...) rather than reaching for the
managers/guards directly. Mirrors `TopographyContext`'s shape.

THE SHIPMENT LINE IS THE UNIT OF TRUTH. THE SESSION IS A LENS ONTO IT.
(intake_portal_workflow.md §5.5.) Every quantity question — how much of a
line has been received, whether it is short, whether another unit may be
linked to it — is answered from ALL live allocations against that line,
across every session. A calculation scoped to a single session is a bug.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.control_layer.errors import (
    InventoryValidationError,
    LineCapacityExceeded,
    RecordingLocked,
)
from app.inventory.control_layer import barcode_tokens
from app.inventory.control_layer.guards.intake_guard import (
    AllocationValidator,
    IntakePolicy,
    IntakeSessionStateMachine,
)
from app.inventory.control_layer.managers.allocation_link_manager import (
    AllocationLinkManager,
)
from app.inventory.control_layer.managers.auto_association_manager import (
    AutoAssociationPolicy,
)
from app.inventory.control_layer.managers.auto_intake_manager import AutoIntakeManager
from app.inventory.control_layer.managers.intake_matching_manager import (
    IntakeMatchingManager,
)
from app.inventory.control_layer.managers.scan_command_manager import (
    ScanCommandHandler,
)
from app.inventory.control_layer.narrators.intake_narrator import IntakeNarrator
from app.inventory.control_layer.session_thread import session_thread
from app.inventory.control_layer.orchestrators.intake_commit_orchestrator import (
    IntakeCommitOrchestrator,
)
from app.inventory.models.intake.enums import (
    AllocationCondition,
    AllocationIntakeMethod,
    AllocationLinkSource,
    IntakeSessionMethod,
    IntakeSessionStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.intake_session_shipment_link import (
    IntakeSessionShipmentLink,
)
from app.inventory.models.intake.item_allocation import ItemAllocation


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
        notes: str = "",
        actor=None,
    ) -> ItemAllocation:
        AllocationValidator.check_quantity_positive(quantity=quantity)
        AllocationValidator.check_serial_implies_unit_qty(
            serial_number=serial_number, quantity=quantity
        )
        AllocationValidator.check_composite_sn_unique(
            part_id=part_id, serial_number=serial_number
        )

        linked = shipment_line_id is not None
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
                link_source=(
                    AllocationLinkSource.MANUAL if linked else AllocationLinkSource.UNLINKED
                ),
                linked_at=timezone.now() if linked else None,
                linked_by=actor if linked else None,
                notes=notes,
                created_by=actor,
                updated_by=actor,
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
        # The serial rides onto the good sibling, so that sibling has to
        # satisfy the serial => qty 1 invariant too (§6.2) — otherwise the
        # new DB constraint rejects the write with a bare IntegrityError.
        if good_qty > 0:
            AllocationValidator.check_serial_implies_unit_qty(
                serial_number=allocation.serial_number, quantity=good_qty
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
                        link_source=allocation.link_source,
                        linked_at=allocation.linked_at,
                        linked_by_id=allocation.linked_by_id,
                        raw_payload=allocation.raw_payload,
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
                        link_source=allocation.link_source,
                        linked_at=allocation.linked_at,
                        linked_by_id=allocation.linked_by_id,
                        raw_payload=allocation.raw_payload,
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

        PHASE 2 REPLACES THE MATCHER. `IntakeMatchingManager.find_target_line`
        predates the auto-association policy in §5.2 — it knows nothing about
        the session's `active_shipment` and does not apply the over-allocation
        cap. Until it is rewritten, a machine-made link is stamped
        `AUTO_SINGLE_MATCH`; the `AUTO_ACTIVE_PACKAGE` flavor has no producer
        yet because there is no active-shipment tie-breaker to produce it.
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
                link_source=(
                    AllocationLinkSource.AUTO_SINGLE_MATCH
                    if target_line is not None
                    else AllocationLinkSource.UNLINKED
                ),
                linked_at=timezone.now() if target_line is not None else None,
                linked_by=actor if target_line is not None else None,
                raw_payload=raw_payload,
                created_by=actor,
                updated_by=actor,
            )

            IntakeMatchingManager.execute_fifo_cascade(session=self.session, part=part)

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
        """Soft-delete sweep across every child row (§5.4): allocations and
        shipment links retract together so nothing survives the session as a
        live orphan.

        Cancelled sessions drop out of every cross-session total — only LIVE
        allocations from non-cancelled sessions count toward a line (§5.5,
        "Scope of other sessions").
        """
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

            session.status = IntakeSessionStatus.CANCELLED
            session.notes = f"{session.notes}\nCancelled: {reason}".strip() if reason else session.notes
            session.updated_by = actor
            session.save(update_fields=["status", "notes", "updated_by", "updated_at"])
        self._session = session
        return session
