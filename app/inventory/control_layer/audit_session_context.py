"""Context: the single public entrypoint for audit control logic (Phase 7).

Callers use domain verbs (`start`, `record_line`, `set_resolution`,
`finalize`, `cancel`) rather than reaching for the guards/managers directly.
Mirrors `IntakeContext`'s shape. `inline_edit` is the stealth single-line
COMPLETED session a direct Active Inventory row edit fabricates behind the
scenes, so every quantity change still lands an `InventoryAuditLog` row.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.control_layer.guards.audit_guard import (
    AuditPolicy,
    AuditSessionStateMachine,
    AuditValidator,
)
from app.inventory.control_layer.managers.stock_ledger_manager import StockLedgerManager
from app.inventory.control_layer.narrators.audit_narrator import AuditNarrator
from app.inventory.control_layer.narrators.movement_narrator import MovementNarrator
from app.inventory.models.audit.audit_session import AuditSession
from app.inventory.models.audit.audit_session_line import AuditSessionLine
from app.inventory.models.audit.enums import (
    AuditReasonCode,
    AuditResolutionType,
    AuditSessionStatus,
    AuditSessionType,
    DiscrepancyType,
)
from app.inventory.models.audit.inventory_audit_log import InventoryAuditLog
from app.inventory.models.movements.enums import MovementType
from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.storage_location import StorageLocation


class AuditSessionContext:
    def __init__(self, audit_session_id: int) -> None:
        self.audit_session_id = audit_session_id
        self._session: AuditSession | None = None

    @property
    def session(self) -> AuditSession:
        if self._session is None:
            self._session = AuditSession.objects.select_related(
                "warehouse", "room", "conducted_by"
            ).get(pk=self.audit_session_id)
        return self._session

    # ------------------------------------------------------------------ #
    # Root creation
    # ------------------------------------------------------------------ #

    @classmethod
    def start(
        cls,
        *,
        warehouse_id: int,
        room_id: int | None = None,
        session_type: str = AuditSessionType.SPOT_CHECK,
        conducted_by,
        actor=None,
        notes: str = "",
    ) -> "AuditSessionContext":
        AuditPolicy.check_can_audit(actor=actor)
        session = AuditSession.objects.create(
            session_number=AuditNarrator.generate_session_number(),
            warehouse_id=warehouse_id,
            room_id=room_id,
            session_type=session_type,
            status=AuditSessionStatus.OPEN,
            conducted_by=conducted_by,
            notes=notes,
            created_by=actor,
            updated_by=actor,
        )
        return cls(session.pk)

    # ------------------------------------------------------------------ #
    # Counting
    # ------------------------------------------------------------------ #

    def record_line(
        self,
        *,
        part_id: int,
        storage_location_id: int | None = None,
        serial_number: str = "",
        counted_qty: Decimal,
        actor=None,
    ) -> AuditSessionLine:
        """Snapshot expected off `ActiveInventory` at entry time and derive
        the variance/discrepancy shape right away — never recomputed later,
        so two lines logged for the same balance in one session both see the
        figure that was true when each was counted."""
        session = self.session
        if session.status != AuditSessionStatus.OPEN:
            raise InventoryValidationError(
                ["Cannot record a count on a session that is not open."]
            )
        AuditPolicy.check_can_audit(actor=actor)
        AuditValidator.check_counted_non_negative(counted_qty=counted_qty)
        AuditValidator.check_serial_count_shape(
            serial_number=serial_number, counted_qty=counted_qty
        )

        storage_location = None
        room = session.room
        if storage_location_id is not None:
            storage_location = StorageLocation.objects.select_related(
                "room_location__room"
            ).get(pk=storage_location_id)
            room = storage_location.room_location.room
        if room is None:
            raise InventoryValidationError(
                ["A storage location (or a session anchored on a room) is "
                 "required to record a count."]
            )
        AuditPolicy.check_domain_access(actor=actor, room=room)

        balance = ActiveInventory.objects.filter(
            room=room,
            storage_location=storage_location,
            part_id=part_id,
            serial_number=serial_number,
        ).first()
        expected_qty = balance.quantity_on_hand if balance else Decimal("0")
        variance_qty = counted_qty - expected_qty
        if variance_qty == 0:
            discrepancy_type = DiscrepancyType.MATCHED
        elif variance_qty > 0:
            discrepancy_type = DiscrepancyType.SURPLUS_FOUND
        else:
            discrepancy_type = DiscrepancyType.DEFICIT_MISSING

        return AuditSessionLine.objects.create(
            session=session,
            part_id=part_id,
            storage_location=storage_location,
            serial_number=serial_number,
            expected_qty=expected_qty,
            counted_qty=counted_qty,
            variance_qty=variance_qty,
            discrepancy_type=discrepancy_type,
            created_by=actor,
            updated_by=actor,
        )

    def set_resolution(
        self, *, line_id: int, resolution_type: str, actor=None
    ) -> AuditSessionLine:
        line = self.session.lines.get(pk=line_id, deleted_at__isnull=True)
        if line.discrepancy_type == DiscrepancyType.MATCHED:
            raise InventoryValidationError(["A matched line needs no resolution."])
        if resolution_type not in AuditResolutionType.values:
            raise InventoryValidationError(
                [f"'{resolution_type}' is not a valid resolution type."]
            )
        line.resolution_type = resolution_type
        line.updated_by = actor
        line.save(
            update_fields=["resolution_type", "updated_by", "updated_at"]
        )
        return line

    # ------------------------------------------------------------------ #
    # Finalize / cancel
    # ------------------------------------------------------------------ #

    def finalize(
        self, *, actor=None, default_reason_code: str = AuditReasonCode.SPOT_COUNT_ADJUSTMENT
    ) -> AuditSession:
        """Atomic: apply every line's variance through `StockLedgerManager`
        (all lines or none — a failure on any line rolls the whole finalize
        back), stamp `last_audited_*` on every counted balance, and write one
        `InventoryAuditLog` row per non-matched line."""
        session = self.session
        AuditSessionStateMachine.check(
            from_status=session.status, to_status=AuditSessionStatus.COMPLETED
        )
        AuditPolicy.check_can_audit(actor=actor)

        lines = list(
            session.lines.filter(deleted_at__isnull=True).select_related(
                "part", "storage_location__room_location__room"
            )
        )
        discrepant = [l for l in lines if l.discrepancy_type != DiscrepancyType.MATCHED]
        unresolved = [l for l in discrepant if not l.resolution_type]
        if unresolved:
            raise InventoryValidationError(
                [
                    f"{len(unresolved)} discrepant line(s) still need a "
                    f"resolution before finalize."
                ]
            )

        matched = surplus = deficit = 0
        with transaction.atomic():
            for line in lines:
                room = (
                    line.storage_location.room_location.room
                    if line.storage_location
                    else session.room
                )
                if line.discrepancy_type == DiscrepancyType.MATCHED:
                    matched += 1
                    self._stamp_audited(
                        room=room,
                        storage_location=line.storage_location,
                        part_id=line.part_id,
                        serial_number=line.serial_number,
                        actor=actor,
                    )
                    continue

                if line.discrepancy_type == DiscrepancyType.SURPLUS_FOUND:
                    surplus += 1
                else:
                    deficit += 1

                if line.resolution_type == AuditResolutionType.DIRECT_ADJUSTMENT:
                    reason_code = default_reason_code
                    self._apply_direct_adjustment(session=session, room=room, line=line, actor=actor)
                else:
                    reason_code = AuditReasonCode.UNRECORDED_TRANSFER
                    self._apply_unrecorded_transfer(session=session, room=room, line=line, actor=actor)

                self._write_log(session=session, line=line, reason_code=reason_code, actor=actor)
                self._stamp_audited(
                    room=room,
                    storage_location=line.storage_location,
                    part_id=line.part_id,
                    serial_number=line.serial_number,
                    actor=actor,
                )

            session.status = AuditSessionStatus.COMPLETED
            session.completed_at = timezone.now()
            session.updated_by = actor
            session.save(
                update_fields=["status", "completed_at", "updated_by", "updated_at"]
            )

        return session

    def cancel(self, *, actor=None) -> AuditSession:
        session = self.session
        AuditSessionStateMachine.check(
            from_status=session.status, to_status=AuditSessionStatus.CANCELLED
        )
        session.status = AuditSessionStatus.CANCELLED
        session.completed_at = timezone.now()
        session.updated_by = actor
        session.save(
            update_fields=["status", "completed_at", "updated_by", "updated_at"]
        )
        return session

    # ------------------------------------------------------------------ #
    # Inline edit — the stealth single-line COMPLETED session.
    # ------------------------------------------------------------------ #

    @classmethod
    def inline_edit(
        cls, *, active_inventory_id: int, new_qty: Decimal, actor=None, notes: str = ""
    ) -> AuditSession | None:
        """A direct row-level quantity edit on `/inventory/active-inventory`,
        wrapped as a one-line DIRECT_INLINE_EDIT session so it lands an
        `InventoryAuditLog` row like any other correction. A zero-variance
        edit is a no-op — nothing is created."""
        balance = ActiveInventory.objects.select_related(
            "warehouse", "room", "storage_location", "part"
        ).get(pk=active_inventory_id)
        AuditPolicy.check_can_audit(actor=actor)
        AuditPolicy.check_domain_access(actor=actor, room=balance.room)
        AuditValidator.check_counted_non_negative(counted_qty=new_qty)

        if new_qty == balance.quantity_on_hand:
            return None

        with transaction.atomic():
            session = AuditSession.objects.create(
                session_number=AuditNarrator.generate_session_number(),
                warehouse=balance.warehouse,
                room=balance.room,
                session_type=AuditSessionType.DIRECT_INLINE_EDIT,
                status=AuditSessionStatus.OPEN,
                conducted_by=actor,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )
            ctx = cls(session.pk)
            line = ctx.record_line(
                part_id=balance.part_id,
                storage_location_id=balance.storage_location_id,
                serial_number=balance.serial_number,
                counted_qty=new_qty,
                actor=actor,
            )
            ctx.set_resolution(
                line_id=line.pk,
                resolution_type=AuditResolutionType.DIRECT_ADJUSTMENT,
                actor=actor,
            )
            ctx.finalize(actor=actor, default_reason_code=AuditReasonCode.INLINE_QUANTITY_EDIT)

        return session

    # ------------------------------------------------------------------ #
    # Finalize helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_direct_adjustment(*, session: AuditSession, room, line: AuditSessionLine, actor) -> None:
        if line.variance_qty > 0:
            StockLedgerManager.inject(
                warehouse=session.warehouse,
                room=room,
                storage_location=line.storage_location,
                part=line.part,
                qty=line.variance_qty,
                serial=line.serial_number,
                actor=actor,
            )
        else:
            StockLedgerManager.withdraw(
                room=room,
                storage_location=line.storage_location,
                part=line.part,
                qty=abs(line.variance_qty),
                serial=line.serial_number,
                actor=actor,
            )

    @staticmethod
    def _apply_unrecorded_transfer(*, session: AuditSession, room, line: AuditSessionLine, actor) -> None:
        """Surplus found here is treated as unrecorded stock that moved in
        from the warehouse's Intake Room; a deficit is treated as stock that
        moved out to it — the same catch-all bucket every other unassigned
        write in this app uses. Writes the paired `PartMovement`
        (`CYCLE_COUNT_ADJUSTMENT`) directly rather than through
        `MovementManager.execute`, since that manager's `classify` never
        produces this movement type."""
        intake_room = session.warehouse.rooms.get(is_intake_room=True)
        qty = abs(line.variance_qty)

        if line.discrepancy_type == DiscrepancyType.SURPLUS_FOUND:
            from_room, from_location = intake_room, None
            to_room, to_location = room, line.storage_location
        else:
            from_room, from_location = room, line.storage_location
            to_room, to_location = intake_room, None

        StockLedgerManager.transfer(
            warehouse=session.warehouse,
            from_room=from_room,
            from_storage_location=from_location,
            to_room=to_room,
            to_storage_location=to_location,
            part=line.part,
            qty=qty,
            serial=line.serial_number,
            actor=actor,
        )
        movement = PartMovement.objects.create(
            movement_number=MovementNarrator.generate_movement_number(),
            part=line.part,
            quantity=qty,
            serial_number=line.serial_number,
            movement_type=MovementType.CYCLE_COUNT_ADJUSTMENT,
            from_warehouse=session.warehouse,
            from_room=from_room,
            from_storage_location=from_location,
            to_warehouse=session.warehouse,
            to_room=to_room,
            to_storage_location=to_location,
            moved_by=actor,
            notes=f"Audit session {session.session_number} — unrecorded transfer resolution.",
            created_by=actor,
            updated_by=actor,
        )
        line.linked_movement = movement
        line.updated_by = actor
        line.save(update_fields=["linked_movement", "updated_by", "updated_at"])

    @staticmethod
    def _write_log(*, session: AuditSession, line: AuditSessionLine, reason_code: str, actor) -> InventoryAuditLog:
        room = (
            line.storage_location.room_location.room
            if line.storage_location
            else session.room
        )
        return InventoryAuditLog.objects.create(
            audit_number=AuditNarrator.generate_log_number(),
            line=line,
            part=line.part,
            warehouse=session.warehouse,
            room=room,
            previous_qty=line.expected_qty,
            new_qty=line.counted_qty,
            variance_qty=line.variance_qty,
            reason_code=reason_code,
            recorded_by=actor,
        )

    @staticmethod
    def _stamp_audited(*, room, storage_location, part_id, serial_number, actor) -> None:
        ActiveInventory.objects.filter(
            room=room,
            storage_location=storage_location,
            part_id=part_id,
            serial_number=serial_number,
        ).update(last_audited_at=timezone.now(), last_audited_by=actor)

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    @staticmethod
    def list_sessions():
        return AuditSession.objects.select_related("warehouse", "room", "conducted_by")

    @staticmethod
    def get_session(session_id: int) -> AuditSession:
        return AuditSessionContext.list_sessions().get(pk=session_id)
