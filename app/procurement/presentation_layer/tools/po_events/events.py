"""Typed event vocabulary for outbound purchase-order transmissions (D48)."""

from __future__ import annotations

from enum import Enum


class PurchaseOrderEventType(str, Enum):
    PO_CREATED = "po_created"
    PO_STATUS_CHANGED = "po_status_changed"
    PO_LINE_CHANGED = "po_line_changed"
    PO_ALLOCATION_CHANGED = "po_allocation_changed"
    PO_RECEIPT_RECORDED = "po_receipt_recorded"
