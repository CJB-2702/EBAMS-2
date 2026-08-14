from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.procurement.models.pricing.enums import PriceConfidence, UnitCostSource


class PurchaseOrderLine(AuditFieldsMixin, SoftDeleteMixin):
    """One line item on a PurchaseOrder.

    No line-level status column (D51). The legacy line carried its own status
    cascaded from the header, so header, line, and demand each held a partial
    copy of the same fact and could disagree. A line's state is its header's
    status; arrival progress is physical — ShipmentLine.quantity_accepted
    against this line.

    Cancellation is a soft delete plus an audit comment, not a status value
    (D57): a cancelled line is deleted_at-stamped, and the record of who, when,
    and a JSON snapshot of the row as it stood lives as a machine comment on
    the PO's Event.

    ONE ACTIVE LINE PER PART PER PO (D58) is enforced in
    PurchaseOrderLineValidator as a soft error, NOT as a database constraint.
    Two reasons: the rule is about pricing simplicity (one part, one price, one
    line) rather than data integrity, so relaxing it later for split delivery
    dates or tiered pricing should be a guard change and not a migration; and
    shipment-line assignment resolves part -> PO line, which is only unambiguous
    while the rule holds — the soft version keeps that failure visible rather
    than impossible. A duplicate that gets through degrades gracefully:
    arriving shipment lines land unassigned rather than mis-assigned.

    No is_fake_for_inventory_adjustments. The legacy line had a boolean marking
    synthetic lines created purely to book an inventory adjustment; a flag that
    makes a commercial document sometimes not a commercial document is exactly
    the kind of overload to leave behind.
    """

    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
    )
    # Auto-assigned as max(existing) + 1 at create; reorderable by the Buyer.
    line_number = models.PositiveIntegerField()

    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    # Line-level override of the header estimate.
    expected_delivery_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    # Price provenance (D85, D88) — what this line's unit_cost is based on.
    # Blank-by-default: pre-existing rows have no answer, and the derived
    # basis rendering treats blank as "not stated" rather than a fourth
    # confidence value.
    unit_cost_source = models.CharField(
        max_length=20, choices=UnitCostSource.choices, blank=True, default=""
    )
    # The observation's observed_at, never today — this is what makes
    # staleness renderable.
    unit_cost_asserted_at = models.DateField(null=True, blank=True)
    # How sure THIS Buyer is about THIS line, distinct from the observation's
    # own confidence on the day it was recorded (D88). The system never
    # downgrades this silently on copy.
    unit_cost_confidence = models.CharField(
        max_length=10, choices=PriceConfidence.choices, blank=True, default=""
    )

    # ── Graph materialization (D79-D82) ─────────────────────────────────────
    # Nullable is a TECHNICAL NECESSITY of the create sequence, not a real
    # "can be ungraphed" state: GraphSummaryManager.initialize_node() assigns
    # this in the same transaction as the line's own creation (D82), so a
    # PurchaseOrderLine is never actually observed with graph_id unset outside
    # that one transaction. Never assigned directly by any other caller — only
    # GraphSummaryManager writes this column (node-init, merge, split).
    graph = models.ForeignKey(
        "procurement.GraphSummary",
        on_delete=models.PROTECT,
        related_name="purchase_order_lines",
        null=True,
        blank=True,
    )

    # Derived values — line_total, quantity_allocated_total,
    # quantity_unallocated, qty_from_accepted_shipments, qty_issued — live on
    # PurchaseOrderLineStruct / PurchaseOrderFulfillmentStruct, never here
    # (D53). The legacy model exposed each as an @property issuing its own
    # query, so rendering a 40-line PO cost well over a hundred queries.

    class Meta:
        db_table = "purchase_order_line"
        ordering = ["purchase_order", "line_number"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_ordered__gt=0),
                name="pol_quantity_ordered_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gte=0),
                name="pol_unit_cost_non_negative",
            ),
            models.UniqueConstraint(
                fields=["purchase_order", "line_number"],
                name="uniq_pol_order_line_number",
            ),
        ]
        indexes = [
            # "Which open POs cover this part" — the splitting wizard's key read.
            models.Index(fields=["part", "purchase_order"], name="pol_part_order_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.purchase_order_id} line {self.line_number}"
