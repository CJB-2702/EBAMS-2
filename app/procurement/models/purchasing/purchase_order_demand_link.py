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

    QUANTITY_RECEIVED REVERSES D55 (superseded — see the Reallocation
    Resolution decision in procurement_current_state_kit/domain_model.md).
    D55 originally rejected a per-claim received quantity because a shared PO
    line's arrival is fungible — nobody decided whose units they were, and any
    attribution a receiver typed would be an invention recorded as fact. That
    objection still holds for an AUTOMATIC split; it does not hold for an
    explicit human decision. `quantity_received` is written only by a
    deliberate Buyer/Receiver action (record_receipt) that manually assigns
    part of a PO line's arrived total across its claiming demands — the same
    kind of explicit, appendable, human-typed decision this app already trusts
    for PurchaseOrderShipmentLink.quantity_allocated. It is never inferred or
    auto-derived, so the fungibility objection to inventing a split does not
    apply to it.

    `is_locked` becomes True the moment `quantity_received > 0` and is never
    cleared except by the Reallocation Portal's deliberate two-popup unlock
    sequence — see reallocation_resolution_kit/reallocation_resolution_portal.md.
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

    # How much of this claim has been manually marked received (Reallocation
    # Resolution decision, superseding D55 — see class docstring). Written
    # only by PurchaseOrderDemandLinkManager.record_receipt, capped so the
    # sum across a line's claims never exceeds that line's own accepted total
    # (app.procurement.control_layer.domain_structs.arrival_allocation).
    quantity_received = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    # True the instant quantity_received > 0; cleared only by the
    # Reallocation Portal's two-popup unlock sequence. Never set back to
    # False by any other path — a source can never be reduced below a locked
    # claim without a deliberate, confirmed override.
    is_locked = models.BooleanField(default=False)

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
            models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0),
                name="podl_quantity_received_non_negative",
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
