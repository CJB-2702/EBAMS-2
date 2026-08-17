"""Narrator: human-readable audit text for the intake domain.

`IntakeSession` carries no `Event`/`Comment` thread of its own (unlike
`Shipment`/`PurchaseOrder`), so this narrator is a pure string factory —
callers persist the text wherever it belongs (`IntakeSession.notes`,
`messages.success`, a future `ItemAllocation`-level log). Mirrors
`PartDemandNarrator`'s shape.
"""

from __future__ import annotations

from decimal import Decimal


class IntakeNarrator:
    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #

    @staticmethod
    def session_started(*, warehouse_code: str, room_name: str, intake_method: str) -> str:
        target = room_name or "the warehouse's Intake Room"
        return f"Intake session started at {warehouse_code} / {target} ({intake_method})."

    @staticmethod
    def shipment_associated(*, shipment_number: str) -> str:
        return f"Shipment {shipment_number} linked to this intake session."

    @staticmethod
    def transitioned_to_reconciling(*, discrepancy_part_count: int) -> str:
        return (
            f"Moved to reconciliation — {discrepancy_part_count} part(s) have a "
            f"discrepancy between expected and allocated quantity."
        )

    @staticmethod
    def session_closed(
        *, good_qty: Decimal, rejected_qty: Decimal, has_unlinked_allocations: bool
    ) -> str:
        flag = " Unlinked (unmanifested) allocations remain quarantined." if (
            has_unlinked_allocations
        ) else ""
        return (
            f"Intake session closed. {good_qty} good / {rejected_qty} rejected "
            f"logged.{flag}"
        )

    @staticmethod
    def session_cancelled(*, reason: str) -> str:
        text = "Intake session cancelled; all allocations and links retracted."
        return f"{text} Reason: {reason}" if reason else text

    # ------------------------------------------------------------------ #
    # Allocations
    # ------------------------------------------------------------------ #

    @staticmethod
    def allocation_created(
        *, part_number: str, quantity: Decimal, condition: str, serial_number: str = ""
    ) -> str:
        serial = f" SN:{serial_number}" if serial_number else ""
        return f"{quantity} x {part_number} logged as {condition}{serial}."

    @staticmethod
    def allocation_split(
        *, part_number: str, good_qty: Decimal, rejected_qty: Decimal
    ) -> str:
        return (
            f"{part_number} allocation split into {good_qty} good / "
            f"{rejected_qty} rejected."
        )

    @staticmethod
    def unmanifested_allocation_quarantined(*, part_number: str, quantity: Decimal) -> str:
        return (
            f"{quantity} x {part_number} received with no matching shipment "
            f"line — quarantined as unmanifested stock."
        )

    # ------------------------------------------------------------------ #
    # Auto Intake
    # ------------------------------------------------------------------ #

    @staticmethod
    def auto_intake_line_delta(
        *, part_number: str, delta_good: Decimal, delta_rejected: Decimal
    ) -> str:
        return (
            f"Auto Intake: {part_number} +{delta_good} good, +{delta_rejected} "
            f"rejected."
        )

    @staticmethod
    def auto_intake_committed(*, shipment_number: str, line_count: int) -> str:
        return (
            f"Auto Intake committed against shipment {shipment_number}: "
            f"{line_count} line(s) processed."
        )

    # ------------------------------------------------------------------ #
    # Reconciliation
    # ------------------------------------------------------------------ #

    @staticmethod
    def reconciliation_task_generated(
        *, part_number: str, expected: Decimal, allocated: Decimal, rejected: Decimal
    ) -> str:
        return (
            f"Reconciliation task opened for {part_number}: expected {expected}, "
            f"allocated {allocated} good / {rejected} rejected."
        )

    @staticmethod
    def reconciliation_line_resolved(
        *, part_number: str, shipment_number: str, resolution_type: str
    ) -> str:
        return (
            f"{part_number} on shipment {shipment_number} resolved as "
            f"'{resolution_type}'."
        )

    @staticmethod
    def reconciliation_parent_auto_resolved(*, part_number: str) -> str:
        return f"All shipment lines for {part_number} resolved — reconciliation closed."

    # ------------------------------------------------------------------ #
    # Commit orchestrator (procurement hand-off)
    # ------------------------------------------------------------------ #

    @staticmethod
    def cumulative_accept_recorded(
        *, part_number: str, shipment_number: str, cumulative_qty: Decimal
    ) -> str:
        return (
            f"{part_number} on shipment {shipment_number}: cumulative accepted "
            f"across all closed intake sessions now {cumulative_qty}."
        )

    @staticmethod
    def shipment_line_split_on_partial_receipt(
        *, part_number: str, shipment_number: str, received_qty: Decimal
    ) -> str:
        return (
            f"{part_number} on shipment {shipment_number}: partial receipt of "
            f"{received_qty} closed this session's portion; the remaining "
            f"balance was split onto a new shipment line still awaiting "
            f"delivery."
        )
