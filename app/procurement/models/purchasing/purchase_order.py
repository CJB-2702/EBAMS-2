from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.procurement.models.purchasing.enums import (
    APPROVAL_STATE_UNSET,
    PurchaseOrderApprovalState,
    PurchaseOrderStatus,
)


class PurchaseOrder(AuditFieldsMixin, SoftDeleteMixin):
    """A commercial order placed with a vendor.

    A peer of PartDemand, never nested under it (D14, R1) — a PO can exist with
    zero linked demands, which is how proactive and bulk restocking is modeled.
    """

    # ── Identity ────────────────────────────────────────────────────────────
    # Format PO-<YYYY-MM-DD>-<8 hex>, generated at create. Carried forward from
    # the legacy generator, which worked.
    po_number = models.CharField(max_length=100, unique=True, db_index=True)
    # Buyer-entered, externally sourced (D71/D77). Not unique on purpose —
    # vendors reuse and mistype their own numbers.
    vendor_po_id = models.CharField(max_length=200, blank=True, db_index=True)

    # A vendor is a commercial supplier, unrelated to parts/manufacturing
    # (D45 superseded) — a vendor may resell parts it does not make.
    vendor = models.ForeignKey(
        "procurement.Vendor",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    # Free string, filled per-PO by the Buyer. This is what dissolves the
    # vendor multi-point-of-contact problem (D41) for this build: per-category
    # contacts are recorded naturally, with nothing modeling them.
    vendor_contact = models.CharField(max_length=200, blank=True)

    # ── Domain scoping ──────────────────────────────────────────────────────
    # The buying domain — who is placing this order, as distinct from the
    # receiving domain on each linked demand. A PO whose lines serve demands
    # across several domains still has exactly one owning domain. Also supplies
    # the domain for the PO's Event row, which requires one.
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )

    # ── Lifecycle (D27) ─────────────────────────────────────────────────────
    # Draft -> Placed -> Partially Received -> Received
    # Draft -> Cancelled ; Placed -> Cancelled
    # A PO is always created as Draft, never directly as Placed (D52): the
    # legacy factory created POs already Ordered, so there was no state in
    # which a PO could be reviewed before the vendor was told.
    status = models.CharField(
        max_length=30,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
    )

    # ── Approval axis (D71/D76) — separate from status ──────────────────────
    # Never assigned directly; moved through PurchaseOrderContext's
    # submit_for_approval/approve_order/deny_order verbs. place() refuses to
    # run unless this is Approved.
    approval_state = models.CharField(
        max_length=30,
        choices=PurchaseOrderApprovalState.choices,
        blank=True,
        default=APPROVAL_STATE_UNSET,
    )

    # ── Dates and money ─────────────────────────────────────────────────────
    order_date = models.DateField()
    expected_delivery_date = models.DateField(null=True, blank=True)

    shipping_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    tax_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    # Other fees, charges, or discounts.
    other_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    # Denormalized: sum(line totals) + shipping + tax + other. Recomputed by
    # PurchaseOrderCostManager on every line write, never set by a caller —
    # same reason purchased_qty is denormalized, a PO list should not sum lines
    # per row.
    total_cost = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    # ── The Event (D17–D19) ─────────────────────────────────────────────────
    # ONE row per PO for its whole lifetime, created alongside the PO — not one
    # per status change. Event rather than ActivityThread specifically because
    # it carries the status/comments/attachments trio this needs. It provides
    # the status history (each change posts a machine comment, D18), the
    # document library for quotes/invoices/packing slips via the Event's
    # existing attachment support (D19), and human comments. There is
    # deliberately no PurchaseOrderUpdate table.
    #
    # Nullable because the Event is created in the same transaction but the FK
    # is set after the Event row exists. The factory guarantees a PO never
    # escapes that transaction without one.
    event = models.OneToOneField(
        "events.Event",
        on_delete=models.PROTECT,
        related_name="purchase_order",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "purchase_order"
        ordering = ["-order_date", "-created_at"]
        indexes = [
            # The Buyer's open-orders queue.
            models.Index(fields=["status", "order_date"], name="po_status_date_idx"),
            # "Everything we've bought from this vendor."
            models.Index(fields=["vendor"], name="po_vendor_idx"),
            # The Purchasing Manager's approval queue.
            models.Index(
                fields=["approval_state"], name="po_approval_state_idx"
            ),
        ]
        permissions = [
            (
                "buy",
                "Can create/edit purchase orders and lines, allocate/de-link "
                "demands, submit for approval, and place orders",
            ),
            ("purchase_approve", "Can approve or deny a purchase order"),
        ]

    def __str__(self) -> str:
        return self.po_number
