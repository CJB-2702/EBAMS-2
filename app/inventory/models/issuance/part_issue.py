from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class PartIssue(AuditFieldsMixin, SoftDeleteMixin):
    """A quantity of material handed to a person against a demand.

    The only table app/inventory/ gets this build (D46). No stock or on-hand
    levels, no storerooms, no locations, no bins, no inventory movements, no
    intake or put-away, no serial tracking, no cycle counts, no adjustments,
    no reservations. The legacy PartIssue carried a source storeroom, location,
    bin, unit_cost_at_issue, an issue_type discriminator, and an asset
    recipient; every one of those is deferred whole to the later Inventory
    build.

    THE WRITE PATH IS THE SEAM, NOT THE TABLE. Creating a row here is not, by
    itself, an issuance: the demand's issued_qty and issuance_state only move
    when PartIssuanceOrchestrator calls PartDemandContext.record_issuance() in
    the same transaction (D12). If a row is ever created outside that call,
    issued_qty drifts silently and procurement cannot detect it, because
    procurement may not look at inventory.

    PROTECT on part_demand is what makes D7 work: procurement's delete guard
    never has to know inventory exists, because the FK blocks the delete for
    free from the consumer side.
    """

    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="issues",
    )
    # The person receiving the material.
    issued_to = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="part_issues",
    )

    # SIGNED. Positive = issued out; negative = returned (D39). A return is a
    # second, negative row against the same demand — not a return table, not a
    # quantity_returned column, not a boolean. The legacy pair
    # (was_borrow_and_return / quantity_returned) was never populated in
    # practice, which is the evidence this shape is the right one.
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    issued_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "part_issue"
        ordering = ["-issued_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity=0),
                name="part_issue_quantity_non_zero",
            ),
        ]
        indexes = [
            models.Index(
                fields=["part_demand", "issued_at"], name="part_issue_demand_at_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Issue #{self.pk}: demand {self.part_demand_id} x{self.quantity}"
