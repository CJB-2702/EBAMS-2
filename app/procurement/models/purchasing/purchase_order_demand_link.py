from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class PurchaseOrderDemandLink(AuditFieldsMixin, SoftDeleteMixin):
    """The many-to-many allocation row between a PartDemand and a
    PurchaseOrderLine.

    A peer join row (M2), not a restricted view of either side: it carries
    attributes belonging to the pairing and to neither side alone.

    Naming lineage: legacy PartDemandPurchaseOrderLink -> M1's DemandSetLine ->
    this (D50). The final name is forward-looking — this will not be the only
    table linking demands to something, so the family reads <thing>DemandLink.

    THERE IS NO quantity_received COLUMN (D55, reversing D26). An earlier draft
    carried one, on the theory that recording receipt against the allocation
    rather than the PO line was what made per-demand fulfillment answerable.
    The problem is not where the number is stored — it is that for a shared PO
    line the number does not exist. Three demands on one line, sixty units
    arrive: the units are fungible, nobody decided whose they were, and any
    attribution a receiver typed would be an invention recorded as an
    observation. Arrival is recorded once, physically, on
    ShipmentLine.quantity_accepted, and per-demand arrival is derived — exact
    for a sole-demand line, a shared demand session otherwise. See
    procurement_starter_kit/shared_demand_sessions.md.
    """

    # PROTECT, not CASCADE — an allocation is exactly what D6 means by
    # "touched", so it must block a hard delete of the demand.
    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    # CASCADE — an allocation to a deleted draft line is meaningless.
    purchase_order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.CASCADE,
        related_name="allocations",
    )

    # How much of this PO line is claimed by this demand. Capped per demand
    # against quantity_requested - purchased_qty (D28), never against the
    # line's remaining quantity — a line is always free to carry more ordered
    # quantity than the sum of its allocations.
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3)

    # Released allocations. Distinct from soft delete:
    #   de-link  — the Buyer changed their mind about this pairing: soft delete.
    #   release  — the PO was cancelled and the vendor is not shipping:
    #              is_active = False, readable as history.
    # Inactive rows are excluded from every purchased_qty sum.
    is_active = models.BooleanField(default=True)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "purchase_order_demand_link"
        ordering = ["-created_at"]
        constraints = [
            # One allocation per pairing. A Buyer who wants more allocates more
            # on the existing row; they never create a second.
            models.UniqueConstraint(
                fields=["part_demand", "purchase_order_line"],
                name="uniq_podl_demand_line",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_allocated__gt=0),
                name="podl_quantity_allocated_positive",
            ),
        ]
        indexes = [
            # The purchased_qty recompute.
            models.Index(
                fields=["part_demand", "is_active"], name="podl_demand_active_idx"
            ),
            # The line's allocation rollup, and the attribution-mode count.
            models.Index(
                fields=["purchase_order_line", "is_active"], name="podl_line_active_idx"
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Demand #{self.part_demand_id} -> line #{self.purchase_order_line_id} "
            f"x{self.quantity_allocated}"
        )
