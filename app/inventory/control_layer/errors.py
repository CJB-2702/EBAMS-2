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


class ReconciliationBarrierError(InventoryValidationError):
    """Session close was attempted while a `PartReconciliationSession` child
    is still PENDING — the close barrier `IntakeCommitOrchestrator` enforces
    before any stock/procurement write runs."""

    def __init__(self, *, session_id: int, pending_part_ids: list[int]) -> None:
        self.session_id = session_id
        self.pending_part_ids = pending_part_ids
        msg = (
            f"Intake session #{session_id} still has unresolved reconciliation "
            f"for part(s) {pending_part_ids} — resolve every discrepancy before "
            f"closing."
        )
        super().__init__([msg])
