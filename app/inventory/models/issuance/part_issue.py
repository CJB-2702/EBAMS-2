from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.inventory.models.issuance.enums import IssueType


class PartIssue(AuditFieldsMixin, SoftDeleteMixin):
    """A quantity of material handed to a person, an asset, or (still, by
    default) a demand.

    THE WRITE PATH IS THE SEAM, NOT THE TABLE. Creating a row here is not, by
    itself, an issuance: for `FOR_PART_DEMAND` rows, the demand's issued_qty
    and issuance_state only move when PartIssuanceOrchestrator calls
    PartDemandContext.record_issuance() in the same transaction (D12). If a
    row is ever created outside that call, issued_qty drifts silently and
    procurement cannot detect it, because procurement may not look at
    inventory. DIRECT_TO_ASSET/DIRECT_TO_USER rows skip procurement entirely
    (Phase 6, FD-5) — there is no demand to keep in sync.

    PROTECT on part_demand is what makes D7 work: procurement's delete guard
    never has to know inventory exists, because the FK blocks the delete for
    free from the consumer side.

    Phase 6 (FD-5) extends this table rather than building the kit's separate
    `PartIssuance` model: issue_type discriminates the three ways a row can
    be anchored, active_inventory/serial_number/unit_cost_at_issue snapshot
    the physical stock provenance at issue time.
    """

    session = models.ForeignKey(
        "inventory.PartIssueSession",
        on_delete=models.PROTECT,
        related_name="issues",
        null=True,
        blank=True,
    )

    issue_type = models.CharField(
        max_length=20, choices=IssueType.choices, default=IssueType.FOR_PART_DEMAND
    )

    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="issues",
        null=True,
        blank=True,
    )
    # The person receiving the material. Nullable (Phase 6) — a
    # DIRECT_TO_ASSET issue may have no individual recipient at all.
    issued_to = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="part_issues",
        null=True,
        blank=True,
    )
    issued_to_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.SET_NULL,
        related_name="received_part_issues",
        null=True,
        blank=True,
    )

    # Stock provenance (Phase 6) — which balance row this issue drew from
    # (or, for a return, was re-injected into). Null for pre-Phase-6 rows and
    # for issues that predate a stock-tracked source.
    from_room = models.ForeignKey(
        "inventory.Room",
        on_delete=models.PROTECT,
        related_name="part_issues",
        null=True,
        blank=True,
    )
    from_storage_location = models.ForeignKey(
        "inventory.StorageLocation",
        on_delete=models.PROTECT,
        related_name="part_issues",
        null=True,
        blank=True,
    )
    serial_number = models.CharField(max_length=200, blank=True, default="")
    unit_cost_at_issue = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
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
            models.CheckConstraint(
                condition=~models.Q(issue_type=IssueType.FOR_PART_DEMAND)
                | models.Q(part_demand__isnull=False),
                name="part_issue_demand_required_for_type",
            ),
            models.CheckConstraint(
                condition=models.Q(part_demand__isnull=False)
                | models.Q(issued_to_asset__isnull=False)
                | models.Q(issued_to__isnull=False),
                name="part_issue_recipient_required",
            ),
        ]
        indexes = [
            models.Index(
                fields=["part_demand", "issued_at"], name="part_issue_demand_at_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"Issue #{self.pk}: demand {self.part_demand_id} x{self.quantity}"
