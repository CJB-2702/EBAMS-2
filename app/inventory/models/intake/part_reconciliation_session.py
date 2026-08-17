from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import ReconciliationStatus


class PartReconciliationSession(AuditFieldsMixin, SoftDeleteMixin):
    """Parent grouping for one part number's discrepancy review within an
    IntakeSession (FD-9). Keyed on `(intake_session, part)` — the operator's
    review UI groups "reconcile M4 screws" here, while the per-shipment-line
    detail (and `resolution_type`) lives on the child `PartReconciliationLine`
    to avoid netting shortages from one vendor shipment against overages from
    another (overages_shortages_and_reconciliation.md §2.1).

    `status` is derived: RESOLVED once every child line is resolved. No
    `resolution_type` column here (FD-9) — that only ever lives on the child.
    """

    intake_session = models.ForeignKey(
        "inventory.IntakeSession",
        on_delete=models.CASCADE,
        related_name="reconciliations",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="intake_reconciliations",
    )
    status = models.CharField(
        max_length=30,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.PENDING,
    )
    total_expected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_allocated_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_rejected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    resolved_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_part_reconciliation_session"
        ordering = ["intake_session", "part"]
        constraints = [
            models.UniqueConstraint(
                fields=["intake_session", "part"],
                name="uniq_reconciliation_session_part",
            ),
        ]

    def __str__(self) -> str:
        return f"Reconciliation #{self.pk}: part {self.part_id} ({self.status})"
