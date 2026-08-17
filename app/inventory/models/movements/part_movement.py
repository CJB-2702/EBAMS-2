from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.inventory.models.movements.enums import MovementType


class PartMovement(AuditFieldsMixin):
    """One physical relocation of stock, always paired with the
    `StockLedgerManager.transfer` call that actually moved the balance
    (Phase 6). Immutable ledger entry — no soft delete, nothing here is ever
    edited after the fact.

    `movement_type` is derived by `MovementManager.classify` from the
    source/destination shape, never chosen by a caller. Serialized transfers
    carry the unit's `serial_number`; non-serialized transfers leave it ''.
    """

    movement_number = models.CharField(max_length=30, unique=True)
    part = models.ForeignKey(
        "parts.Part", on_delete=models.PROTECT, related_name="movements"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    serial_number = models.CharField(max_length=200, blank=True, default="")
    movement_type = models.CharField(max_length=40, choices=MovementType.choices)

    from_warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.PROTECT, related_name="movements_from"
    )
    from_room = models.ForeignKey(
        "inventory.Room", on_delete=models.PROTECT, related_name="movements_from"
    )
    from_storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="movements_from",
        null=True,
        blank=True,
    )

    to_warehouse = models.ForeignKey(
        "inventory.Warehouse", on_delete=models.PROTECT, related_name="movements_to"
    )
    to_room = models.ForeignKey(
        "inventory.Room", on_delete=models.PROTECT, related_name="movements_to"
    )
    to_storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="movements_to",
        null=True,
        blank=True,
    )

    moved_by = models.ForeignKey(
        "administration.User", on_delete=models.PROTECT, related_name="part_movements"
    )
    movement_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "part_movement"
        ordering = ["-movement_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="part_movement_quantity_positive",
            ),
        ]
        indexes = [
            models.Index(
                fields=["part", "movement_date"], name="part_movement_part_at_idx"
            ),
            models.Index(
                fields=["movement_type", "movement_date"],
                name="part_movement_type_at_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.movement_number}: {self.part_id} x{self.quantity}"
