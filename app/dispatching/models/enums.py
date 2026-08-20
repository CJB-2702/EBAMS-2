"""Enum vocabulary shared across the dispatching data layer.

DispatchScope, DispatchWorkflowStatus, and RejectionCategory live on
DispatchingDetail itself (app/events/models/details/dispatching.py), since
that model stays in the events app — see build_phase_1_models.md §4.
"""

from django.db import models


class ReservationStatus(models.TextChoices):
    """dispatching_starter_kit/3_asset_reservations.md §9."""

    TENTATIVE = "tentative", "Tentative"
    CONFIRMED = "confirmed", "Confirmed"
    USER_CHECKED_OUT = "user_checked_out", "User Checked Out"
    CHECKED_OUT = "checked_out", "Checked Out"
    USER_RETURNED = "user_returned", "User Returned"
    RETURNED = "returned", "Returned"
    CANCELLED = "cancelled", "Cancelled"
    NO_SHOW = "no_show", "No Show"


class ReservationType(models.TextChoices):
    """dispatching_starter_kit/3_asset_reservations.md §6. A rough consumer
    label, never a counterparty record."""

    WORK = "work", "Work"
    CUSTOMER = "customer", "Customer"
    RENTAL = "rental", "Rental"
    MAINTENANCE = "maintenance", "Maintenance"
    TRANSFER = "transfer", "Transfer"
    OTHER = "other", "Other"


class ReservationUpdateChangeType(models.TextChoices):
    """dispatching_starter_kit/3_asset_reservations.md §8."""

    RESCHEDULE = "reschedule", "Reschedule"
    ASSET_SWAP = "asset_swap", "Asset Swap"
    STATUS_TRANSITION = "status_transition", "Status Transition"
    CANCELLATION = "cancellation", "Cancellation"
    EXTENSION = "extension", "Extension"
    OTHER = "other", "Other"


class ExpenseType(models.TextChoices):
    """dispatching_starter_kit/4_dispatch_line_items.md §3. Contract and
    reimbursement are one record, distinguished by type only."""

    CONTRACT = "contract", "Contract"
    REIMBURSEMENT = "reimbursement", "Reimbursement"


class ExpenseStatus(models.TextChoices):
    """dispatching_starter_kit/4_dispatch_line_items.md §4."""

    PLANNED = "planned", "Planned"
    COMMITTED = "committed", "Committed"
    COMPLETE = "complete", "Complete"
    CANCELLED = "cancelled", "Cancelled"


class ConditionRating(models.TextChoices):
    """Operational vocabulary, kept from legacy per HANDOFF.md §9 — confirmed
    against /home/cb/REPOS/asset_management/app/data/dispatching/
    dispatch_manifest/dispatch_asset.py."""

    GOOD = "good", "Good"
    FAIR = "fair", "Fair"
    POOR = "poor", "Poor"
    DAMAGED = "damaged", "Damaged"


class PersonnelRole(models.TextChoices):
    """Operational vocabulary, kept from legacy per HANDOFF.md §9 — confirmed
    against /home/cb/REPOS/asset_management/app/data/dispatching/
    dispatch_manifest/dispatch_personnel.py."""

    DRIVER = "driver", "Driver"
    PASSENGER = "passenger", "Passenger"
    OPERATOR = "operator", "Operator"
    CREW_CHIEF = "crew_chief", "Crew Chief"
    OBSERVER = "observer", "Observer"
    OTHER = "other", "Other"
