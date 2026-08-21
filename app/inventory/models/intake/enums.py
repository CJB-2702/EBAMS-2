"""Status/choice vocabulary for the intake domain (FD-8's "no magic strings"
rule, applied here). One module so every model, guard, and manager imports
the same values.
"""

from __future__ import annotations

from django.db import models


class IntakeSessionStatus(models.TextChoices):
    """IntakeSession.status — DRAFT -> ACTIVE -> CLOSED, with CANCELLED
    reachable from any non-CLOSED state (see IntakeSessionStateMachine in
    guards/intake_guard.py for the legal-transition table).

    This is a coarse DISPLAY label maintained by the control layer, not the
    authority on session state (intake_portal_workflow.md §11.4). The
    authority is the pair of event stamps on IntakeSession —
    `recording_locked_at/_by` and `stock_posted_at/_by` — because each one
    answers *who* and *when*, which an enum position never could.

    `RECONCILING` was removed with the reconciliation tables (§12.7): there
    is no such stage any more. Association and reconciliation are abstract,
    revisitable activities that happen at any point in a session's life,
    never stages in a pipeline (§4.1).
    """

    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"


class IntakeSessionMethod(models.TextChoices):
    """How the session's allocations were produced. SCAN is Phase 5 (barcode
    scanning engine). MANUAL_PACKAGE is the Auto Intake portal's pseudo-session
    (FD-13)."""

    SCAN = "scan", "Scan"
    MANUAL_PACKAGE = "manual_package", "Manual Package (Auto Intake)"


class AllocationCondition(models.TextChoices):
    GOOD = "good", "Good"
    REJECTED = "rejected", "Rejected"


class AllocationIntakeMethod(models.TextChoices):
    """How the COUNT was captured. Not how the link was decided — that is
    `AllocationLinkSource`, and the two are deliberately separate columns."""

    SCAN = "scan", "Scan"
    MANUAL = "manual", "Manual"


class AllocationLinkSource(models.TextChoices):
    """How an ItemAllocation came to point at its shipment line
    (intake_portal_workflow.md §12.3).

    The record page auto-links behind every scan (§5.2), so audit must be
    able to tell a machine guess from a human decision — and to tell the
    *confident* guess (the part number appears on exactly one line in the
    whole session manifest) from the *contextual* one (it was on the active
    shipment). UNLINKED is a real, terminal, non-exceptional state, not a
    null: excess physical stock stays unlinked by design (§7.2).
    """

    UNLINKED = "unlinked", "Unlinked"
    AUTO_SINGLE_MATCH = "auto_single_match", "Auto — Single Match"
    AUTO_ACTIVE_PACKAGE = "auto_active_package", "Auto — Active Shipment"
    MANUAL = "manual", "Manual"
