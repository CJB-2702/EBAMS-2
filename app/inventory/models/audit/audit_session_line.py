from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.audit.enums import AuditResolutionType, DiscrepancyType


class AuditSessionLine(AuditFieldsMixin, SoftDeleteMixin):
    """One counted part/location within an `AuditSession`. `expected_qty` is
    snapshotted off `ActiveInventory` at the moment the line is recorded, not
    recomputed at finalize — two counters logging the same balance in one
    session should see the same expected figure.

    `linked_movement` is only set for `UNRECORDED_TRANSFER` resolutions, once
    `AuditSessionContext.finalize` has created the paired `PartMovement`.
    """

    session = models.ForeignKey(
        "inventory.AuditSession",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="audit_session_lines",
    )
    storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="audit_session_lines",
        null=True,
        blank=True,
    )
    serial_number = models.CharField(max_length=200, blank=True, default="")
    expected_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    counted_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    variance_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    discrepancy_type = models.CharField(
        max_length=20,
        choices=DiscrepancyType.choices,
        default=DiscrepancyType.MATCHED,
    )
    resolution_type = models.CharField(
        max_length=30,
        choices=AuditResolutionType.choices,
        blank=True,
        default="",
    )
    linked_movement = models.ForeignKey(
        "inventory.PartMovement",
        on_delete=models.SET_NULL,
        related_name="audit_session_lines",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "inventory_audit_session_line"
        ordering = ["session", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(counted_qty__gte=0),
                name="audit_session_line_counted_qty_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"AuditSessionLine #{self.pk}: part {self.part_id} ({self.discrepancy_type})"
