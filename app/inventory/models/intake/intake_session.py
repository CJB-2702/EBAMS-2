from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import IntakeSessionMethod, IntakeSessionStatus


class IntakeSession(AuditFieldsMixin, SoftDeleteMixin):
    """One receiving run by an operator (FD-10, FD-13).

    THE SHIPMENT LINE IS THE UNIT OF TRUTH. THE SESSION IS A LENS ONTO IT.
    (intake_portal_workflow.md §5.5.) A session is a display filter over a
    shipment-line-grain truth, never an accounting boundary. Any calculation
    scoped to a single session is a bug: allocations from *every* live
    session count toward a line's received quantity, its progress bars, and
    its discrepancies.

    `warehouse` anchors the session — required. `room` is optional; when null,
    stock posting targets the warehouse's protected Intake Room
    (`WarehouseFactory.intake_room`) rather than a `dock_location` model that
    was never built (FD-10 supersedes the kit's `dock_location_id` field).

    `intake_method` distinguishes a human walking the floor with a scanner
    (Phase 5) from the Auto Intake portal's pseudo-session (`MANUAL_PACKAGE`,
    FD-13), which is created and immediately committed in one call.

    State lives in two INDEPENDENT event stamps, not in `status` (§4.2, §11.4):

      recording_locked_at/_by   non-null => the record page is read-only.
                                Set only when the user explicitly says so;
                                nothing auto-locks (§4.3).
      stock_posted_at/_by       non-null => stock has merged into the general
                                pool. The only one-way door in the system,
                                and all-or-nothing — there is no partial
                                posting of clean lines (§4.3, Q8).

    There is deliberately NO third stamp. Paperwork does not lock at all
    (§4.4): cross-session visibility would make a paperwork lock a
    distributed-state problem, so it is dropped rather than made to lie.

    `status` survives as a coarse display label maintained by the control
    layer; the stamps above are the authority.
    """

    operator = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
    )
    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.PROTECT,
        related_name="intake_sessions",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=30,
        choices=IntakeSessionStatus.choices,
        default=IntakeSessionStatus.DRAFT,
    )
    intake_method = models.CharField(
        max_length=30,
        choices=IntakeSessionMethod.choices,
        default=IntakeSessionMethod.MANUAL_PACKAGE,
    )

    # The tie-breaker for auto-association (§5.1). Its ONLY job is to say
    # which shipment the operator is physically standing in front of when a
    # part number appears on more than one line in the manifest. Stored
    # rather than held in the session cookie so it survives F5 and is
    # visible to anyone else looking at the page.
    active_shipment = models.ForeignKey(
        "procurement.Shipment",
        on_delete=models.PROTECT,
        related_name="active_in_intake_sessions",
        null=True,
        blank=True,
    )

    # Display-only continuation reference (§7.5). Nothing reads it,
    # aggregates across it, or validates against it — it exists so a human
    # reading session #12 can see it followed session #8. DO NOT BUILD
    # LOGIC ON IT.
    continues_session = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="continued_by",
        null=True,
        blank=True,
    )

    # Comments + file attachments for this receipt (§8). Nullable and created
    # lazily on first write by `events.ActivityThreadManager`, the same way
    # Part/PartRevision/SupplierItem/DispatchExpense carry theirs.
    activity_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="intake_session_thread",
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(default=timezone.now)

    recording_locked_at = models.DateTimeField(null=True, blank=True)
    recording_locked_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    stock_posted_at = models.DateTimeField(null=True, blank=True)
    stock_posted_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )

    hardware_device_id = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_intake_session"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["operator", "status"], name="intake_session_op_status_idx"),
        ]

    def __str__(self) -> str:
        return f"IntakeSession #{self.pk} ({self.status}) @ {self.warehouse_id}"
