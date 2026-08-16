from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class ShipmentLine(AuditFieldsMixin, SoftDeleteMixin):
    """ONE PHYSICAL LINE ITEM, exactly as the packing slip described it.

    A child of one parent — the shipment it arrived in. Which PO line(s) it
    answers is NOT a column here (D90): that is a commercial mapping, it is
    many-to-many, and it lives on PurchaseOrderShipmentLink.

    This row used to carry a nullable `purchase_order_line` FK, with a line
    spanning several PO lines resolved by splitting it into sibling rows. That
    made the physical record and the commercial mapping the same column, so
    recording a mapping meant destructively rewriting an arrived quantity. Now
    the two are separate: this row is what showed up and never changes to
    accommodate paperwork, and allocations are appendable rows beside it. See
    PurchaseOrderShipmentLink's docstring for the full reversal argument.

    Consequently there is no `split_from` column either — nothing splits, so
    there is no lineage to preserve.
    """

    shipment = models.ForeignKey(
        "procurement.Shipment",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="shipment_lines",
    )

    # As shipped / as claimed by the packing slip.
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    # As accepted after inspection. A QUANTITY, NOT A BOOLEAN: partial
    # acceptance — 8 good, 2 damaged — is the normal outcome of a damaged
    # shipment, and a boolean would force someone to record a whole shipment as
    # accepted or rejected when neither is true.
    #
    # NULL until someone inspects, which is meaningfully different from 0
    # (inspected, all rejected). Only quantity_accepted counts toward
    # qty_from_accepted_shipments — an uninspected line contributes nothing.
    #
    # THIS IS THE ONLY PLACE ACCEPTANCE IS RECORDED (D90). Inspection is
    # physical and happens once, to the box; it is not repeated per PO line.
    # Per-PO-line arrival is derived from this by allocation share, in exactly
    # one function — see domain_structs/arrival_allocation.py.
    quantity_accepted = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    # Why the difference, when there is one.
    rejection_notes = models.TextField(blank=True)

    # ── Graph materialization (D79-D82) ─────────────────────────────────────
    # Nullable is a TECHNICAL NECESSITY of the create sequence, not a real
    # "can be ungraphed" state: GraphSummaryManager.initialize_node() assigns
    # this in the same transaction as the line's own creation (D82), so a
    # ShipmentLine is never actually observed with graph_id unset outside
    # that one transaction. Never assigned directly by any other caller —
    # only GraphSummaryManager writes this column (node-init, merge, split).
    graph = models.ForeignKey(
        "procurement.GraphSummary",
        on_delete=models.PROTECT,
        related_name="shipment_lines",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "shipment_line"
        ordering = ["shipment", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="shpline_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_accepted__isnull=True)
                | models.Q(quantity_accepted__gte=0),
                name="shpline_quantity_accepted_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["shipment", "part"], name="shpline_shp_part_idx"),
            models.Index(fields=["graph"], name="shpline_graph_idx"),
        ]

    def __str__(self) -> str:
        return f"Shipment #{self.shipment_id} / part {self.part_id} x{self.quantity}"
