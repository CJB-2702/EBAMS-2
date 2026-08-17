"""Status/choice vocabulary for the intake domain (FD-8's "no magic strings"
rule, applied here). One module so every model, guard, and manager imports
the same values.
"""

from __future__ import annotations

from django.db import models


class IntakeSessionStatus(models.TextChoices):
    """IntakeSession.status — DRAFT -> ACTIVE -> RECONCILING -> CLOSED, with
    CANCELLED reachable from any non-CLOSED state (see IntakeSessionStateMachine
    in guards/intake_guard.py for the legal-transition table). ACTIVE -> CLOSED
    directly is also legal — the Auto Intake path never touches reconciliation
    because partial receipts are resolved by splitting the shipment line
    (FD-27), not by a reconciliation task."""

    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    RECONCILING = "reconciling", "Reconciling"
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
    SCAN = "scan", "Scan"
    MANUAL = "manual", "Manual"


class ReconciliationStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"


class ReconciliationResolutionType(models.TextChoices):
    """Declared on PartReconciliationLine (the child), never on the parent
    PartReconciliationSession (FD-9) — resolution is a per-shipment-line fact,
    to avoid netting shortages from one vendor shipment against overages from
    another for the same part number."""

    NONE = "none", "None"
    ACCEPTED_SHORTAGE = "accepted_shortage", "Accepted Shortage"
    QUARANTINED_OVERAGE = "quarantined_overage", "Quarantined Overage"
    FORCE_ACCEPTED_OVERAGE = "force_accepted_overage", "Force Accepted Overage"
    RMA_DISPOSITION = "rma_disposition", "RMA Disposition"
