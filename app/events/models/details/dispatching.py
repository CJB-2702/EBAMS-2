from django.db import models

from app.events.models.event import Event, EventType


class DispatchScope(models.TextChoices):
    ON_SITE = "on_site", "On-site"
    LOCAL = "local", "Local"
    REGIONAL = "regional", "Regional"
    NATIONAL = "national", "National"
    INTERNATIONAL = "international", "International"


class DispatchWorkflowStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    UNDER_REVIEW = "under_review", "Under Review"
    FIXES_REQUESTED = "fixes_requested", "Fixes Requested"
    PLANNED = "planned", "Planned"
    ALTERNATE_RESOLUTION = "alternate_resolution", "Alternate Resolution"
    REJECTED = "rejected", "Rejected"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class RejectionCategory(models.TextChoices):
    RESOURCE_UNAVAILABLE = "resource_unavailable", "Resource Unavailable"
    POLICY_VIOLATION = "policy_violation", "Policy Violation"
    TIMING_CONFLICT = "timing_conflict", "Timing Conflict"
    OTHER = "other", "Other"


class DispatchingDetail(Event):
    """
    Detail table for event_type='dispatching'. The dispatch itself — a stated
    need for transport or equipment plus the record of how it was met.

    There is no separate "request" object (dispatching_starter_kit/2_dispatch.md
    §1). What legacy called a request and a dispatch is one record here,
    distinguished only by workflow_status. Reservations and expenses attach to
    this row as line items (see dispatching.AssetReservation,
    dispatching.DispatchExpense) — there is no "outcome" concept and nothing is
    selected among them.

    workflow_status is deliberately separate from the inherited Event.status:
    the dispatch lifecycle (requested/under_review/.../completed) is not
    the generic Event vocabulary (planned/in_progress/complete/...), and legacy's
    duplicate status field is exactly the drift this split avoids.
    """

    requested_for = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="dispatches_requested_for",
    )
    requested_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatches_requested_by",
    )

    workflow_status = models.CharField(
        max_length=30,
        choices=DispatchWorkflowStatus.choices,
        default=DispatchWorkflowStatus.REQUESTED,
    )

    desired_start = models.DateTimeField()
    desired_end = models.DateTimeField()

    headcount = models.PositiveIntegerField(null=True, blank=True)
    names_free_text = models.TextField(
        blank=True,
        help_text="Who is travelling, including non-system people.",
    )

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="dispatches",
    )
    asset_subclass_text = models.CharField(max_length=255, blank=True)

    # DELIBERATE ANTI-PATTERN-ADJACENT WARNING (not an anti-pattern — a guard
    # against one): informational only, never a reference. Written once at
    # request time and never updated again — not when a reservation is made,
    # not when one is cancelled, not when an asset is swapped. It is a
    # historical record of what was asked for, nothing more. The reservations
    # attached to this dispatch (dispatching.AssetReservation) are the only
    # authority on what asset is actually committed. DO NOT sync this field
    # from reservations — that is the single most likely "helpful" bug this
    # column will attract. See dispatching_starter_kit/2_dispatch.md §4 and
    # design_drift.md §2.8.
    requested_assets = models.TextField(
        blank=True,
        help_text=(
            "Informational and historical only — what was asked for, written once "
            "at request time. Never synced from reservations. The dispatch's "
            "reservations are the sole authority on what is actually committed."
        ),
    )

    dispatch_scope = models.CharField(
        max_length=20,
        choices=DispatchScope.choices,
        blank=True,
    )
    estimated_meter_usage = models.FloatField(null=True, blank=True)
    activity_location = models.CharField(max_length=255, blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)

    previous_dispatch = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="superseding_dispatches",
    )
    created_from_revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatches_created",
    )

    # ── Rejection — lives on the dispatch itself, never a child record ───────
    # See dispatching_starter_kit/2_dispatch.md §9. Terminal; resubmission is a
    # new dispatch linked back via previous_dispatch, not an in-place edit.
    rejection_reason = models.TextField(blank=True)
    rejection_category = models.CharField(
        max_length=30,
        choices=RejectionCategory.choices,
        blank=True,
    )
    rejected_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatches_rejected",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    alternative_suggestion = models.TextField(blank=True)
    can_resubmit = models.BooleanField(default=True)
    resubmit_after = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "event_detail_dispatching"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(desired_start__lte=models.F("desired_end")),
                name="dispatch_desired_window_ordered",
            ),
            models.CheckConstraint(
                condition=~models.Q(workflow_status="rejected")
                | ~models.Q(rejection_reason=""),
                name="dispatch_rejection_requires_reason",
            ),
        ]
        permissions = [
            ("dispatch_raise", "Can create a dispatch, edit own while editable, submit, cancel own"),
            ("dispatch_plan", "Can view the queue, take a dispatch under review, request fixes, set priority"),
            ("dispatch_reject", "Can formally refuse a dispatch with a reason"),
            ("dispatch_complete", "Can mark a dispatch completed; cancel any dispatch"),
            ("dispatching_read", "Read-only access to every dispatching record"),
        ]

    def save(self, *args, **kwargs) -> None:
        self.event_type = EventType.DISPATCHING
        super().save(*args, **kwargs)
