"""Narrator: human-readable audit text for the intake domain.

A pure string factory — callers persist the text wherever it belongs. As of
intake_portal_workflow.md §8 an `IntakeSession` DOES carry a thread of its
own (`IntakeSession.activity_thread`, nullable, created lazily by
`events.ActivityThreadManager`), so machine comments belong there. Phase 2
wires the writes; this module only produces the strings. Mirrors
`PartDemandNarrator`'s shape.

Rejection reasons deliberately have no column (§7.6) — when an item is
marked rejected the reason becomes a comment on the session's activity
thread, prefixed with the line identifier as plain text. NOTHING PARSES
THAT PREFIX. It is a human breadcrumb.
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
    def stock_posted(*, good_qty: Decimal, rejected_qty: Decimal) -> str:
        """The irreversible act (§4.3). `has_unlinked_allocations` is gone as
        a flag (§12.2) — unlinked is NORMAL, not an exception worth
        announcing, and the count is derived live where it matters."""
        return (
            f"Stock posted. {good_qty} good / {rejected_qty} rejected logged. "
            f"This cannot be undone."
        )

    @staticmethod
    def recording_locked() -> str:
        return "Recording locked — no further items can be counted on this session."

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
    def allocation_left_unlinked(*, part_number: str, quantity: Decimal) -> str:
        """Not an error (§5.3, §7.2). Silent non-association is the default
        and correct outcome; unlinked is a terminal state, not a pending
        task. Worded as an explanation, never a failure."""
        return (
            f"{quantity} x {part_number} recorded but not linked to a shipment "
            f"line — held as excess in the intake room."
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
