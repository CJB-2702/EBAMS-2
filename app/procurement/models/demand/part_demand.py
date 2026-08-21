from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.procurement.models.demand.enums import (
    PURCHASING_STATE_UNSET,
    DemandPriority,
    DemandSourceModule,
    DemandState,
    IssuanceState,
    PurchasingState,
    ShipmentState,
)
from app.procurement.models.graph.enums import LinearStatus


class PartDemand(AuditFieldsMixin, SoftDeleteMixin):
    """The hub (G3). A material need moving from request through approval,
    purchasing, shipping, and physical hand-off.

    The rest of this app and every consumer app knows only PartDemand.id.
    Consumer apps (Maintenance, Dispatching, Inventory) own their own link
    tables pointing inward at this row; there is never a pointer outward (D7).
    """

    # ── Identity and subject ────────────────────────────────────────────────
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="demands",
    )
    notes = models.TextField(blank=True)
    priority = models.CharField(
        max_length=20,
        choices=DemandPriority.choices,
        default=DemandPriority.MEDIUM,
    )
    needed_by = models.DateTimeField(null=True, blank=True)

    # Who asked. Distinct from created_by, which may be a consumer app's
    # service actor rather than a person.
    requested_by = models.ForeignKey(
        "administration.User",
        on_delete=models.PROTECT,
        related_name="requested_part_demands",
        null=True,
        blank=True,
    )
    expected_cost = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # ── The four state axes (D32) ───────────────────────────────────────────
    # Snapshot columns — a live cache of the PartDemandUpdate journal. NEVER
    # assigned directly by any caller. Every change goes through
    # PartDemandStateManager.transition(), which writes the journal row and
    # refreshes the snapshot in one transaction. If the two ever disagree, the
    # journal wins and these are rebuildable from it.
    demand_state = models.CharField(
        max_length=30,
        choices=DemandState.choices,
        default=DemandState.PROJECTED,
    )
    # Blank (not NULL) is the meaningful default: "no purchasing decision has
    # been made", which is a real state rather than missing data. Kept as a
    # blank CharField so the column, the journal's stage columns, and the
    # transition dicts all speak one type.
    purchasing_state = models.CharField(
        max_length=30,
        choices=PurchasingState.choices,
        blank=True,
        default=PURCHASING_STATE_UNSET,
    )
    shipment_state = models.CharField(
        max_length=40,
        choices=ShipmentState.choices,
        default=ShipmentState.REQUEST_NOT_SENT,
    )
    issuance_state = models.CharField(
        max_length=40,
        choices=IssuanceState.choices,
        default=IssuanceState.NOT_ISSUED,
    )

    # ── Pipeline position, inherited from the parent graph ──────────────────
    # A FIFTH STATUS, independent of the four axes above and deliberately not
    # one of them. The axes are about approval, funding, physical logistics,
    # and hand-off — four specialist questions. This answers the one question
    # a non-procurement reader actually asks: "where is this in the pipeline?"
    #
    # DERIVED FROM THE PARENT GRAPH, not from this row. A demand's fulfillment
    # progress is a property of the whole cluster it belongs to — the PO lines
    # covering it and the shipments arriving against them are graph members,
    # not demand columns. Refreshed whenever graph membership changes (merge,
    # split, node-init) and whenever the parent graph recalculates.
    #
    # Never assigned directly by a caller, same discipline as the four axes,
    # but note it does NOT go through PartDemandStateManager.transition() and
    # writes no journal row — it is a cache of someone else's derivation, not
    # a state this demand transitions through on its own.
    linear_status = models.CharField(
        max_length=40,
        choices=LinearStatus.choices,
        default=LinearStatus.UNLINKED,
    )

    # ── Quantities ──────────────────────────────────────────────────────────
    # Named quantity_requested deliberately, never bare `quantity` (D31) —
    # four quantity-flavored fields exist across two models.
    quantity_requested = models.DecimalField(max_digits=12, decimal_places=3)

    # Denormalized summaries, refreshed alongside the writes that change them,
    # never assigned by a caller. purchased_qty is the sum of active
    # PurchaseOrderDemandLink.quantity_allocated.
    purchased_qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )
    # NET, not a running total (D39). May legitimately be 0 after a full
    # return, and may exceed or fall short of both purchased_qty and
    # quantity_requested with no validation blocking it (D30). Maintained only
    # by PartDemandContext.record_issuance() — see the seam note below.
    issued_qty = models.DecimalField(
        max_digits=12, decimal_places=3, default=0
    )

    # ── Origin and tracking flags (D38) ─────────────────────────────────────
    source = models.CharField(
        max_length=50,
        choices=DemandSourceModule.choices,
        default=DemandSourceModule.PROCUREMENT,
        db_index=True,
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="part_demands",
    )
    # Declared upstream, consumed by a future Inventory app. Nothing in this
    # build reads it.
    serial_number_tracking_required = models.BooleanField(default=False)

    # ── Domain scoping (D5) ─────────────────────────────────────────────────
    # Exactly one domain assignment, mandatory. Unlike parts.Part there is no
    # is_domain_limited escape hatch and no access-mapping many-to-many — a
    # demand identifies who is meant to receive the part, and that is always
    # exactly one answer.
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="part_demands",
    )

    # ── Graph materialization (D79-D82) ─────────────────────────────────────
    # Nullable is a TECHNICAL NECESSITY of the create sequence, not a real
    # "can be ungraphed" state: GraphSummaryManager.initialize_node() assigns
    # this in the same transaction as the row's own creation (D82), so a
    # PartDemand is never actually observed with graph_id unset outside that
    # one transaction. Never assigned directly by any other caller — only
    # GraphSummaryManager writes this column (node-init, merge, split).
    graph = models.ForeignKey(
        "procurement.GraphSummary",
        on_delete=models.PROTECT,
        related_name="demands",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "part_demand"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_requested__gt=0),
                name="part_demand_quantity_requested_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(purchased_qty__gte=0),
                name="part_demand_purchased_qty_non_negative",
            ),
        ]
        indexes = [
            # The Approver queue read.
            models.Index(fields=["demand_state", "domain"], name="pd_state_domain_idx"),
            # The Buyer's "what needs buying" read.
            models.Index(
                fields=["purchasing_state", "demand_state"], name="pd_purch_state_idx"
            ),
            # The PO wizard's "find demands for this part" read.
            models.Index(fields=["part", "demand_state"], name="pd_part_state_idx"),
            # Priority ordering in the Buyer's queue.
            models.Index(fields=["needed_by"], name="pd_needed_by_idx"),
            # Source & Event lookup.
            models.Index(fields=["source", "event"], name="pd_source_event_idx"),
        ]
        permissions = [
            (
                "request",
                "Can create and edit demands (viewing does not require this)",
            ),
            (
                "demand_manage",
                "Can transition demand_state and issuance_state on any demand "
                "in-domain, not only demands they raised",
            ),
        ]

    def __str__(self) -> str:
        return f"Demand #{self.pk}: {self.part_id} x{self.quantity_requested}"
