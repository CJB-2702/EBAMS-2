from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DispatchDemandLink(AuditFieldsMixin):
    """Points inward at procurement.PartDemand — mirrors
    maintenance.MaintenanceDemandLink. A material need raises a real,
    issuable demand in the shared hub the moment the dispatch states it;
    there is no dispatching-private parts wish list.
    See dispatching_starter_kit/2_dispatch.md §7."""

    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="demand_links",
    )
    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="dispatching_links",
    )

    class Meta:
        db_table = "dispatch_demand_link"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "part_demand"],
                name="uq_dispatch_demand_link",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} -> Demand #{self.part_demand_id}"
