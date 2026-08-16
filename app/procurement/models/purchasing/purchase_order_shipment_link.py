from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class PurchaseOrderShipmentLink(AuditFieldsMixin, SoftDeleteMixin):
    """The many-to-many allocation row between a ShipmentLine and a
    PurchaseOrderLine (D90).

    THIS REVERSES THE SPLIT-INSTEAD-OF-LINK-TABLE DECISION. ShipmentLine used
    to carry a single `purchase_order_line` FK, and a physical line item
    answering several PO lines was handled by SPLITTING IT INTO SIBLING ROWS.
    That draft's objection to a link table was that an arriving line's quantity
    and the sum of its links can disagree, giving two numbers for one physical
    fact — the legacy ArrivalLine.quantity_available_for_linking problem.

    The objection does not survive contact with the rule this table enforces.
    The sum of a line's active allocations is capped at the line's own
    quantity (PurchaseOrderShipmentLinkValidator.check_allocation), so the
    difference between them is never a discrepancy — it is the UNALLOCATED
    REMAINDER, a real and ordinary business state meaning "this much arrived
    and nobody has said which order it answers yet." That state already
    existed under the old design as a null FK; the only thing that changed is
    that it is now a quantity rather than a whole-row boolean.

    What splitting cost, and this does not: a receiver had to perform an
    explicit destructive edit — mutating the arrived quantity on a physical
    record and creating sibling rows — in order to record a mapping. The
    physical record and the commercial mapping were the same column, so one
    could not be corrected without rewriting the other. Here the shipment line
    stays exactly as the packing slip described it, forever, and every
    commercial decision about it is an appendable, soft-deletable row beside
    it.

    THERE IS NO quantity_accepted COLUMN HERE (D90), deliberately, following
    the same reasoning as PurchaseOrderDemandLink (D55). Inspection is
    physical and happens once, per arriving line, on
    ShipmentLine.quantity_accepted. Per-PO-line arrival is DERIVED from that
    by allocation share — exactly one function does it, and it is documented
    at length: see control_layer/domain_structs/arrival_allocation.py.

    There is also no `is_active` column, unlike its PurchaseOrderDemandLink
    sibling. That table needs one because a cancelled PO releases an
    allocation without the Buyer having changed their mind about the pairing —
    two different kinds of un-linking that must stay distinguishable. No such
    second kind exists here: an allocation between an arrived line and a PO
    line is either right or it is a mistake, and a mistake is a soft delete.
    """

    # CASCADE — an allocation against a hard-deleted arriving line is
    # meaningless. (Soft deletes, which are the normal path, cascade nothing;
    # ShipmentContext.delete_line deactivates the links explicitly.)
    shipment_line = models.ForeignKey(
        "procurement.ShipmentLine",
        on_delete=models.CASCADE,
        related_name="purchase_order_links",
    )
    # PROTECT — an allocation is a receipt against this line, so it must block
    # a hard delete of the PO line the same way a demand allocation does.
    purchase_order_line = models.ForeignKey(
        "procurement.PurchaseOrderLine",
        on_delete=models.PROTECT,
        related_name="shipment_links",
    )

    # How much of the arriving line answers this PO line. Capped against the
    # shipment line's own quantity across all active allocations — see the
    # class docstring on why that cap is what makes the link table honest.
    quantity_allocated = models.DecimalField(max_digits=12, decimal_places=3)

    notes = models.TextField(blank=True)

    class Meta:
        db_table = "purchase_order_shipment_link"
        ordering = ["shipment_line", "id"]
        constraints = [
            # One allocation per pairing. A receiver correcting the amount
            # edits the existing row; they never create a second.
            models.UniqueConstraint(
                fields=["shipment_line", "purchase_order_line"],
                name="uniq_posl_shipment_po_line",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity_allocated__gt=0),
                name="posl_quantity_allocated_positive",
            ),
        ]
        indexes = [
            # The shipment detail page's per-line allocation rollup.
            models.Index(fields=["shipment_line"], name="posl_shipment_line_idx"),
            # The PO fulfillment struct's key read, and the graph adjacency
            # edge lookup.
            models.Index(
                fields=["purchase_order_line"], name="posl_po_line_idx"
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Shipment line #{self.shipment_line_id} -> PO line "
            f"#{self.purchase_order_line_id} x{self.quantity_allocated}"
        )
