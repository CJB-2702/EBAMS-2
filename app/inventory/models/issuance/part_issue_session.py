from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.issuance.enums import IssueSessionStatus, IssueType


class PartIssueSession(AuditFieldsMixin, SoftDeleteMixin):
    """Header record representing a transaction session where one or more
    PartIssue lines were issued at the same time.

    Provides a formal terminal state (`COMMITTED`) for part issuance workflows,
    grouping stock allocations and demand fulfillments executed in the same batch.
    """

    session_number = models.CharField(max_length=50, unique=True)
    issue_type = models.CharField(
        max_length=20, choices=IssueType.choices, default=IssueType.FOR_PART_DEMAND
    )
    status = models.CharField(
        max_length=20, choices=IssueSessionStatus.choices, default=IssueSessionStatus.COMMITTED
    )

    issued_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="authorized_issue_sessions",
    )
    issued_to = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="received_issue_sessions",
        null=True,
        blank=True,
    )
    issued_to_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="received_issue_sessions",
        null=True,
        blank=True,
    )

    issued_at = models.DateTimeField(default=timezone.now)
    issue_reason = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "part_issue_session"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["session_number"], name="part_issue_sess_num_idx"),
            models.Index(fields=["status", "issued_at"], name="part_issue_sess_stat_idx"),
        ]

    def __str__(self) -> str:
        return f"Issue Session #{self.session_number} ({self.get_status_display()})"
