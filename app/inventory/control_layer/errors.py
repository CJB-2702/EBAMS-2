"""Shared control-layer exceptions for the inventory app.

One module so every guard, manager, and factory raises the same classes.
"""

from __future__ import annotations


class InventoryValidationError(Exception):
    """Input or invariant check failed at a boundary."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class InsufficientStockError(InventoryValidationError):
    """A withdraw/transfer attempted to remove more than is on hand."""

    def __init__(self, *, part_id: int, requested, available) -> None:
        self.part_id = part_id
        self.requested = requested
        self.available = available
        msg = (
            f"Cannot withdraw {requested} of part #{part_id} — only "
            f"{available} on hand at that location."
        )
        super().__init__([msg])


class SerialInUseError(InventoryValidationError):
    """A serial number is already carried by another live stock row."""

    def __init__(self, *, part_id: int, serial_number: str) -> None:
        self.part_id = part_id
        self.serial_number = serial_number
        msg = (
            f"Serial number '{serial_number}' is already in stock for "
            f"part #{part_id}."
        )
        super().__init__([msg])


class SvgUploadError(InventoryValidationError):
    """A Room/RoomLocation layout SVG upload failed size or shape validation
    (FD-25/FD-29 — sanitization/reconciliation constraints)."""


class DomainAccessDenied(InventoryValidationError):
    """The acting user does not cover the room's effective data domains."""

    def __init__(self, *, room_id: int) -> None:
        self.room_id = room_id
        msg = f"You do not have data-domain access to room #{room_id}."
        super().__init__([msg])


class IntakeShipmentDomainAccessDenied(InventoryValidationError):
    """The acting user does not cover the shipment's data domain (IntakePolicy)."""

    def __init__(self, *, shipment_id: int) -> None:
        self.shipment_id = shipment_id
        msg = f"You do not have data-domain access to shipment #{shipment_id}."
        super().__init__([msg])


class BarcodeParseError(InventoryValidationError):
    """A scanned payload didn't match any supported barcode format (plain
    SKU, `SKU;SERIAL`, GS1-128 bracketed AI notation, or a raw GS1-128
    digit stream) — `IntakeMatchingManager.parse_barcode` raises this
    instead of crashing the scan request, so the scan portal can fall back
    to manual entry."""

    def __init__(self, *, raw_payload: str) -> None:
        self.raw_payload = raw_payload
        msg = (
            f"Could not read barcode payload '{raw_payload}' — enter the "
            f"item manually."
        )
        super().__init__([msg])


class LineCapacityExceeded(InventoryValidationError):
    """A link would push a shipment line past its quantity — the
    over-allocation ban (intake_portal_workflow.md §7.2).

    THIS IS AN EXPLANATION, NOT A FAULT. The physical stock is real and
    already counted; it simply has nowhere on this line to go, so it stays
    unlinked as excess. The message is worded for an operator holding a box,
    and callers on the auto-association path swallow it entirely (§5.3) —
    the operator is never shown a linking failure.
    """

    def __init__(
        self, *, shipment_line_id: int, part_number: str, expected, already_linked,
        requested,
    ) -> None:
        self.shipment_line_id = shipment_line_id
        self.part_number = part_number
        self.expected = expected
        self.already_linked = already_linked
        self.requested = requested
        self.remaining = max(expected - already_linked, 0)
        msg = (
            f"This line is fully allocated ({already_linked}/{expected} of "
            f"{part_number}). {requested} more cannot be filed against it — "
            f"that stock stays unlinked as excess."
        )
        super().__init__([msg])


class RecordingLocked(InventoryValidationError):
    """A write was attempted against a session whose recording is locked
    (§4.3). Recording locks only when a user explicitly says so, and once
    locked it stays locked — editing a locked session is deliberately out of
    scope for this build (§4.5). If more items need counting, the operator
    opens a second session, which may reference the first (§7.5)."""

    def __init__(self, *, session_id: int) -> None:
        self.session_id = session_id
        super().__init__(
            [
                f"Recording is locked on intake session #{session_id}. Open a "
                f"new session to count more items."
            ]
        )


class StockAlreadyPosted(InventoryValidationError):
    """Stock posting is the one-way door (§4.2). Once stock merges into the
    general pool its per-receipt traceability is gone, so there is nothing to
    reverse into."""

    def __init__(self, *, session_id: int) -> None:
        self.session_id = session_id
        super().__init__(
            [f"Stock has already been posted for intake session #{session_id}."]
        )
