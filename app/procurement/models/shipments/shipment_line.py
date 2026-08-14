from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class ShipmentLine(AuditFieldsMixin, SoftDeleteMixin):
    """A child of two parents: the shipment it physically arrived in, and the
    PO line it fulfills.

    What replaced the link table: an earlier draft used a
    PurchaseOrderShipmentLink many-to-many mirroring the legacy
    ArrivalPurchaseOrderLink. It is gone. A shipment line points at exactly ONE
    PO line by FK; a physical line item spanning several PO lines is handled by
    SPLITTING IT INTO SIBLING ROWS, not by a link table with quantities.

    That is better for a specific reason: with a link table, an arriving line's
    quantity and the sum of its links can disagree, so there are two numbers
    for one physical fact and a reconciliation problem between them — which the
    legacy design carried as ArrivalLine.quantity_available_for_linking, a
    column existing only to describe a discrepancy the schema made possible.
    With splitting, each row's quantity IS the fact and the rows sum to the
    shipment by construction. The cost is that splitting is an explicit user
    action, which is why it gets a wizard.
    """

    shipment = models.ForeignKey(
        "procurement.Shipment",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    # Copied from the header's PO at create, reassignable afterward. NULLABLE:
    # a line can arrive matching nothing on any PO — a vendor substitution, a
    # wrong shipment, a bonus item. It is recorded with a null PO line and
    # surfaced by the fulfillment struct as unassigned, rather than being
    # dropped or forced onto an ill-fitting line.
    purchase_order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.PROTECT,
        related_name="shipment_lines",
        null=True,
        blank=True,
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
    quantity_accepted = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True
    )
    # Why the difference, when there is one.
    rejection_notes = models.TextField(blank=True)

    # Set on lines produced by the splitting wizard, preserving lineage so the
    # original physical line item stays reconstructible.
    split_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="splits",
        null=True,
        blank=True,
    )

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
            # The fulfillment struct's key read.
            models.Index(
                fields=["purchase_order_line", "shipment"], name="shpline_pol_shp_idx"
            ),
            models.Index(fields=["shipment", "part"], name="shpline_shp_part_idx"),
            models.Index(fields=["graph"], name="shpline_graph_idx"),
        ]

    def __str__(self) -> str:
        return f"Shipment #{self.shipment_id} / part {self.part_id} x{self.quantity}"
