from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class MaintenanceDemandLink(AuditFieldsMixin, SoftDeleteMixin):
    """
    D7 Architecture Link Table.
    Points inward at procurement.PartDemand. Zero outward references exist on PartDemand.
    """
    action = models.ForeignKey(
        "maintenance.Action",
        on_delete=models.CASCADE,
        related_name="demand_links",
    )
    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="maintenance_links",
    )
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "maintenance_demand_link"
        ordering = ["sequence_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["action", "part_demand"],
                name="uq_maintenance_action_part_demand",
            )
        ]

    def __str__(self) -> str:
        return f"Link Action={self.action_id} -> Demand={self.part_demand_id}"
