from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.procurement.models.demand.enums import DemandDimension


class PartDemandUpdate(AuditFieldsMixin):
    """One row per transition, on any of the four axes.

    Append-only: rows are never updated, never deleted, never soft-deleted —
    hence AuditFieldsMixin without SoftDeleteMixin, deliberately.

    This table exists because of a specific failure in the legacy hub:
    approval_status got real audit columns while issue_status and order_status
    got none, so there was no record of who marked something issued or why an
    order status moved. Tracking state as bare columns makes that the natural
    outcome — the first dimension gets audit columns and later ones get
    skipped. One uniform journal for all four axes removes the choice.

    Written only by PartDemandStateManager, together with the snapshot column
    it mirrors, in one transaction. There is no code path that writes one
    without the other.
    """

    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.CASCADE,
        related_name="updates",
    )
    dimension = models.CharField(max_length=20, choices=DemandDimension.choices)

    # The value the axis moved TO. Not FK-constrained to an enum table — it is
    # validated against the dimension's TextChoices in the guard, per D22's
    # fixed-hardcoded-enum rule. Blank is legal: it is the value of an unset
    # purchasing_state.
    stage = models.CharField(max_length=40, blank=True)
    # The value it moved FROM. Blank on the four initializing rows.
    previous_stage = models.CharField(max_length=40, blank=True)

    # Nullable because derived transitions — the D43 Completed rollup, and
    # PO-driven axis propagation — have no human actor.
    actor = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="part_demand_updates",
        null=True,
        blank=True,
    )
    # True for derived/propagated transitions. Lets a UI distinguish "the Buyer
    # marked this" from "this followed from a PO status change".
    is_system_generated = models.BooleanField(default=False)

    # Optional free text even for Rejected/Cancelled (D15). No mandatory reason
    # is enforced — a required field here would be filled with "n/a" in a week.
    notes = models.TextField(blank=True)

    # Set when a guard failed open (D13): the transition went through but could
    # not be verified.
    flagged_for_review = models.BooleanField(default=False)

    class Meta:
        db_table = "part_demand_update"
        ordering = ["created_at"]
        indexes = [
            # The demand-history read, which is the only common query.
            models.Index(
                fields=["part_demand", "created_at"], name="pdu_demand_created_idx"
            ),
            # Cross-demand reporting ("everything that hit Backordered").
            models.Index(fields=["dimension", "stage"], name="pdu_dimension_stage_idx"),
            # The fail-open review queue.
            models.Index(
                fields=["flagged_for_review"],
                condition=models.Q(flagged_for_review=True),
                name="pdu_flagged_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Demand #{self.part_demand_id} {self.dimension} -> {self.stage or '(unset)'}"
