from django.db import models
from django.utils import timezone

from app.inventory.models.audit.enums import AuditReasonCode


class InventoryAuditLog(models.Model):
    """Append-only ledger: every quantity change to `ActiveInventory` outside
    intake/movement/issuance is traceable to a row here. No soft delete, no
    update/delete code path anywhere in the control layer — mirrors
    `PartMovement`'s immutable-ledger shape.
    """

    audit_number = models.CharField(max_length=30, unique=True)
    line = models.ForeignKey(
        "inventory.AuditSessionLine",
        on_delete=models.PROTECT,
        related_name="log_entries",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="audit_log_entries",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="audit_log_entries",
    )
    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.PROTECT,
        related_name="audit_log_entries",
    )
    previous_qty = models.DecimalField(max_digits=12, decimal_places=3)
    new_qty = models.DecimalField(max_digits=12, decimal_places=3)
    variance_qty = models.DecimalField(max_digits=12, decimal_places=3)
    reason_code = models.CharField(max_length=30, choices=AuditReasonCode.choices)
    recorded_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="audit_log_entries",
    )

    class Meta:
        db_table = "inventory_audit_log"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["part", "recorded_at"], name="audit_log_part_at_idx"),
            models.Index(fields=["reason_code", "recorded_at"], name="audit_log_reason_at_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.audit_number}: part {self.part_id} {self.previous_qty} -> {self.new_qty}"
