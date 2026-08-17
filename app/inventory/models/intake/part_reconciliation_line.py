from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import ReconciliationResolutionType


class PartReconciliationLine(AuditFieldsMixin, SoftDeleteMixin):
    """Child of PartReconciliationSession: the per-shipment-line discrepancy
    grain (FD-9). Carries the quantities AND the `resolution_type` — the
    parent never does — so a shortage on one vendor's line is never netted
    against an overage on another vendor's line for the same part.
    """

    part_reconciliation_session = models.ForeignKey(
        "inventory.PartReconciliationSession",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    shipment_line = models.ForeignKey(
        "procurement.ShipmentLine",
        on_delete=models.PROTECT,
        related_name="intake_reconciliation_lines",
    )
    expected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    allocated_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    rejected_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    resolution_type = models.CharField(
        max_length=50,
        choices=ReconciliationResolutionType.choices,
        default=ReconciliationResolutionType.NONE,
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "inventory_part_reconciliation_line"
        ordering = ["part_reconciliation_session", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["part_reconciliation_session", "shipment_line"],
                name="uniq_reconciliation_line_shipment_line",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"ReconciliationLine #{self.pk}: shipment_line {self.shipment_line_id} "
            f"({self.resolution_type})"
        )
