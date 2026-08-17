"""Status/choice vocabulary for the audit domain (Phase 7)."""

from __future__ import annotations

from django.db import models


class AuditSessionType(models.TextChoices):
    """How an `AuditSession` was opened. DIRECT_INLINE_EDIT is the stealth
    single-line COMPLETED session `AuditSessionContext.inline_edit` creates
    behind an Active Inventory row's inline quantity edit — never chosen by a
    caller starting a session by hand."""

    FULL_ROOM_AUDIT = "full_room_audit", "Full Room Audit"
    SPOT_CHECK = "spot_check", "Spot Check"
    DIRECT_INLINE_EDIT = "direct_inline_edit", "Direct Inline Edit"


class AuditSessionStatus(models.TextChoices):
    """OPEN -> COMPLETED/CANCELLED (see `AuditSessionStateMachine` in
    guards/audit_guard.py for the legal-transition table)."""

    OPEN = "open", "Open"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class DiscrepancyType(models.TextChoices):
    MATCHED = "matched", "Matched"
    SURPLUS_FOUND = "surplus_found", "Surplus Found"
    DEFICIT_MISSING = "deficit_missing", "Deficit / Missing"


class AuditResolutionType(models.TextChoices):
    """How a non-matched `AuditSessionLine` variance was settled at
    finalize."""

    DIRECT_ADJUSTMENT = "direct_adjustment", "Direct Adjustment"
    UNRECORDED_TRANSFER = "unrecorded_transfer", "Unrecorded Transfer"


class AuditReasonCode(models.TextChoices):
    """`InventoryAuditLog.reason_code` — why an `ActiveInventory` quantity
    changed outside intake/movement/issuance."""

    SPOT_COUNT_ADJUSTMENT = "spot_count_adjustment", "Spot Count Adjustment"
    INLINE_QUANTITY_EDIT = "inline_quantity_edit", "Inline Quantity Edit"
    UNRECORDED_TRANSFER = "unrecorded_transfer", "Unrecorded Transfer"
    DAMAGE_SCRAP = "damage_scrap", "Damage / Scrap"
