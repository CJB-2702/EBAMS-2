from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.intake.enums import AllocationCondition, AllocationIntakeMethod


class ItemAllocation(AuditFieldsMixin, SoftDeleteMixin):
    """One physical unit (or counted batch) logged against an IntakeSession.

    `shipment_line = NULL` means unmanifested/excess — quarantined stock with
    no matching packing-slip line (overages_shortages_and_reconciliation.md
    §1.1). `composite_sn` is `f"{part_id}:{serial_number}"`, written by the
    control layer (never here — models hold no business logic), and is what
    `AllocationValidator` checks for duplicates against both this session's
    other live allocations and existing `ActiveInventory`.
    """

    intake_session = models.ForeignKey(
        "inventory.IntakeSession",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    shipment_line = models.ForeignKey(
        "procurement.ShipmentLine",
        on_delete=models.PROTECT,
        related_name="intake_allocations",
        null=True,
        blank=True,
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="intake_allocations",
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    serial_number = models.CharField(max_length=200, blank=True, default="")
    composite_sn = models.CharField(max_length=400, blank=True, default="", db_index=True)
    condition = models.CharField(
        max_length=30,
        choices=AllocationCondition.choices,
        default=AllocationCondition.GOOD,
    )
    intake_method = models.CharField(
        max_length=30,
        choices=AllocationIntakeMethod.choices,
        default=AllocationIntakeMethod.MANUAL,
    )

    class Meta:
        db_table = "inventory_item_allocation"
        ordering = ["intake_session", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="item_allocation_quantity_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["shipment_line"], name="item_alloc_shp_line_idx"),
            models.Index(fields=["composite_sn"], name="item_alloc_composite_sn_idx"),
        ]

    def __str__(self) -> str:
        serial = f" SN:{self.serial_number}" if self.serial_number else ""
        return f"Allocation #{self.pk}: part {self.part_id} x{self.quantity}{serial} ({self.condition})"
