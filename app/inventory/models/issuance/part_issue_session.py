from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.issuance.enums import IssueReason


class PartIssueSession(AuditFieldsMixin, SoftDeleteMixin):
    """A RECEIPT: one handover of material to one person, at one moment.

    NOT a preparatory session. There is no walk-the-floor gap between staging
    and committing, so there is no DRAFT row, no reservation, and no handoff
    to another operator — the in-progress queue lives in `request.session`
    (`presentation_layer.tools.issuance_draft`) and this table is only ever
    written at the instant the parts change hands. That is the whole reason
    there is no `status` column: an `IssueSessionStatus` enum existed with
    DRAFT and CANCELLED values that nothing could ever write, and a three-state
    field with one reachable state is worse than no field. Contrast
    `IntakeSession`, which IS a preparatory session and earns its status guard.

    THE HEADER OWNS THE RECIPIENT. `issued_to` is non-null and authoritative:
    every `PartIssue` line under this session is written with the same
    recipient, so the two can never disagree. The previous shape carried a
    recipient on both header and line with the line silently winning, which
    made the portal's recipient dropdown decorative.

    Demand-fulfilment only, for now. `issue_type` and `issued_to_asset` were
    removed from this header because every session is FOR_PART_DEMAND; both
    survive on `PartIssue` for the later direct-issue work.
    """

    session_number = models.CharField(max_length=50, unique=True)

    issued_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="authorized_issue_sessions",
    )
    # Non-null by definition: a handover has a recipient.
    issued_to = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="received_issue_sessions",
    )

    issued_at = models.DateTimeField(default=timezone.now)
    issue_reason = models.CharField(
        max_length=30, choices=IssueReason.choices, default=IssueReason.OTHER
    )
    issue_reason_detail = models.CharField(max_length=255, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "part_issue_session"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["issued_to", "issued_at"], name="part_issue_sess_to_idx"),
            models.Index(fields=["issued_at"], name="part_issue_sess_at_idx"),
        ]

    def __str__(self) -> str:
        return f"Issue Session #{self.session_number}"
