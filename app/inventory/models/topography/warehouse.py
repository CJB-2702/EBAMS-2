from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class Warehouse(AuditFieldsMixin, SoftDeleteMixin):
    """A physical stock-holding site under one division. Schema and
    constraints only — provisioning (including its protected Intake Room) is
    `WarehouseFactory`'s job, per FD-14."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    division = models.ForeignKey(
        "administration.Division",
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    address = models.TextField(blank=True)
    domains = models.ManyToManyField(
        "administration.Domain",
        related_name="warehouses",
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_warehouse"
        ordering = ["name"]
        permissions = [
            ("can_manage_topography", "Can create/edit warehouses, rooms, and storage locations"),
            ("can_intake_stock", "Can receive and put away stock into inventory"),
            ("can_move_stock", "Can move stock between storage locations"),
            ("can_issue_parts", "Can issue parts out of stock"),
            ("can_audit_stock", "Can run and resolve inventory audit sessions"),
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.name}"
