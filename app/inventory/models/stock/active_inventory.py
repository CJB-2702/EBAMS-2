from datetime import timedelta
from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ActiveInventory(AuditFieldsMixin):
    """The one stock-balance table (FD-11 — `UnassignedInventory` and
    `InventoryItem` are purged names, never recreated). "Unassigned" is a
    state (`room` = the warehouse's Intake Room, `storage_location = NULL`,
    `is_unassigned = True`), never a table.

    `serial_number` is `''` rather than `NULL` for non-serialized rows
    (FD-12) so `Unique(room, storage_location, part, serial_number)` is
    enforceable on SQLite as well as Postgres — `NULL != NULL` would let
    duplicate aggregate rows slip past a nullable column.

    `StockLedgerManager` is the only writer to this table (Phase 2 goal).
    """

    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.CASCADE,
        related_name="stock",
    )
    room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.CASCADE,
        related_name="stock",
    )
    storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="stock",
        null=True,
        blank=True,
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="stock_balances",
    )
    serial_number = models.CharField(max_length=200, blank=True, default="")
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_cost_avg = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    is_unassigned = models.BooleanField(default=False)
    last_audited_at = models.DateTimeField(null=True, blank=True)
    last_audited_by = models.ForeignKey(
        "administration.User",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "inventory_active_inventory"
        ordering = ["room", "storage_location", "part"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "storage_location", "part", "serial_number"],
                name="uniq_active_inventory_balance",
            ),
            models.CheckConstraint(
                condition=models.Q(serial_number="")
                | models.Q(quantity_on_hand__lte=1),
                name="active_inventory_serialized_unit_row",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_on_hand__gte=0),
                name="active_inventory_qty_on_hand_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_allocated__gte=0),
                name="active_inventory_qty_allocated_non_negative",
            ),
        ]

    def __str__(self) -> str:
        serial = f" SN:{self.serial_number}" if self.serial_number else ""
        return f"{self.part_id} @ {self.room_id}/{self.storage_location_id}{serial} = {self.quantity_on_hand}"

    @property
    def is_stale(self) -> bool:
        if not self.last_audited_at:
            return True
        return self.last_audited_at < timezone.now() - timedelta(days=30)
