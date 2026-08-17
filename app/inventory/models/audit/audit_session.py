from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.audit.enums import AuditSessionStatus, AuditSessionType


class AuditSession(AuditFieldsMixin, SoftDeleteMixin):
    """One ground-truth counting run — a full room audit, a spot check, or
    the stealth single-line session `AuditSessionContext.inline_edit`
    fabricates behind a direct quantity edit on an Active Inventory row
    (Phase 7).

    `room` is optional: a full room audit anchors on one room, but a spot
    check may span a handful of storage locations across a warehouse without
    naming a single room.
    """

    session_number = models.CharField(max_length=30, unique=True)
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="audit_sessions",
    )
    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.PROTECT,
        related_name="audit_sessions",
        null=True,
        blank=True,
    )
    session_type = models.CharField(
        max_length=30,
        choices=AuditSessionType.choices,
        default=AuditSessionType.SPOT_CHECK,
    )
    status = models.CharField(
        max_length=20,
        choices=AuditSessionStatus.choices,
        default=AuditSessionStatus.OPEN,
    )
    conducted_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="audit_sessions",
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_audit_session"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "started_at"], name="audit_session_status_at_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.session_number} ({self.status})"
