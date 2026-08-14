from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.procurement.models.shipments.enums import ShipmentStatus


class Shipment(AuditFieldsMixin, SoftDeleteMixin):
    """What the vendor actually shipped — against a purchase order, or received
    reactively with none yet on file.

    Shipments live in procurement, not inventory (D59), because a shipment in
    transit is PRE-POSSESSION. A shipment line is still a child of a PO line
    when one exists, every FK points into procurement, and nothing about a
    shipment references a storeroom, a bin, or a stock level.

    D71/D73 REVERSES D59's "never free-floating" rule: a shipment can now be
    received before its PO exists (the reactive receiving entry point). A
    shipment is never free of a Domain, though — #4 below is what a PO-less
    shipment still answers "whose is this" with.

    INTAKE IS OUT OF SCOPE. A shipment says what arrived. Accepting into stock,
    put-away, bin assignment, and stock levels are the later Inventory build.
    The line between them is exactly where ShipmentLine.quantity_accepted stops.

    The legacy app merged the two concepts into ArrivalHeader/ArrivalLine,
    which was simultaneously "a shipment that arrived" and "the receiving
    transaction" — that conflation is why receipts there could only ever be
    attributed to PO lines, never to demands.
    """

    # The PRIMARY PO, now optional (D71/D73). One PO has many shipments. Lines
    # may point at other POs' lines — see mixed_po_assignments. A shipment
    # received before its PO exists is linked later via
    # ShipmentContext.attach_purchase_order.
    purchase_order = models.ForeignKey(
        "procurement.PurchaseOrder",
        on_delete=models.PROTECT,
        related_name="shipments",
        null=True,
        blank=True,
    )
    # Required (D71/D74). Copied from the PO's domain when one is supplied at
    # create; chosen by the receiver otherwise. purchase_order going nullable
    # means D68's "no column needed, walk purchase_order.domain" reasoning no
    # longer holds — there may be no purchase_order to walk.
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="shipments",
    )
    # ONE row per shipment for its whole lifetime (D68), same shape as
    # PurchaseOrder.event — status history as machine comments, document
    # library via attachments. Nullable because it is created in the same
    # transaction and the FK is set after the Event row exists; the factory
    # guarantees a shipment never escapes that transaction without one.
    event = models.OneToOneField(
        "events.Event",
        on_delete=models.PROTECT,
        related_name="shipment",
        null=True,
        blank=True,
    )
    shipment_number = models.CharField(max_length=100, unique=True, db_index=True)
    # Renamed from tracking_number (D71/D75). Deliberately not unique — a
    # vendor's own tracking number is reused and mistyped, and not an integer
    # — a numeric column would eat leading zeros.
    shipment_id = models.CharField(max_length=200, blank=True, db_index=True)
    carrier = models.CharField(max_length=200, blank=True)

    # Set True the moment a split creates a sibling row for one of this
    # shipment's lines (D69). A plain full-quantity reassignment does NOT set
    # it — only an actual split does. Maintained by ShipmentLineSplitHandler,
    # never set by a caller. Locks the shipment out of the bulk drag-and-drop
    # tool alongside a Delivered/Accepted status.
    has_splits = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.AWAITING_SHIPMENT,
    )

    # Drift flag. A shipment's lines COPY their PO link from the header at
    # creation; lines can then be reassigned to a line on a different PO, which
    # is legitimate — one physical box routinely holds items from several
    # orders to the same vendor. Set True whenever any line's PO differs from
    # the header's. Maintained by ShipmentLineManager on every line write, never
    # set by a caller.
    #
    # It is a FLAG, NOT A CONSTRAINT. Nothing is blocked. It exists so the
    # condition is queryable rather than discovered by someone puzzling over
    # why a PO's shipment rollup does not add up.
    mixed_po_assignments = models.BooleanField(default=False)

    shipped_date = models.DateField(null=True, blank=True)
    expected_arrival_date = models.DateField(null=True, blank=True)
    # When it physically showed up.
    received_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "shipment"
        ordering = ["-created_at"]
        indexes = [
            # The PO's shipment list.
            models.Index(
                fields=["purchase_order", "status"], name="shp_order_status_idx"
            ),
            # The drift review queue.
            models.Index(
                fields=["mixed_po_assignments"],
                condition=models.Q(mixed_po_assignments=True),
                name="shp_mixed_po_idx",
            ),
            # The domain-scoped receiving queue, including PO-less shipments.
            models.Index(fields=["domain", "status"], name="shp_domain_status_idx"),
        ]
        permissions = [
            (
                "receive",
                "Can create shipments, advance shipment status, inspect and accept lines",
            ),
        ]

    def __str__(self) -> str:
        return self.shipment_number
