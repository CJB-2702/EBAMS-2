"""Narrator: human-readable audit text for the issuance domain. Pure string
factory, same shape as `IntakeNarrator`/`PartDemandNarrator` — callers persist
the text wherever it belongs (`PartIssue.notes`, `messages.success`)."""

from __future__ import annotations

from decimal import Decimal


class IssuanceNarrator:
    @staticmethod
    def issued(
        *, part_number: str, quantity: Decimal, recipient: str, serial_number: str = ""
    ) -> str:
        serial = f" SN:{serial_number}" if serial_number else ""
        return f"{quantity} x {part_number}{serial} issued to {recipient}."

    @staticmethod
    def returned(
        *, part_number: str, quantity: Decimal, recipient: str, serial_number: str = ""
    ) -> str:
        serial = f" SN:{serial_number}" if serial_number else ""
        return f"{quantity} x {part_number}{serial} returned by {recipient}."
