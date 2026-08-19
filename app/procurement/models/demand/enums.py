"""The four state axes of a PartDemand, plus its origin/priority enums.

Four independent dimensions, not one status field (D32). Each is a fixed,
hardcoded TextChoices — identical for every demand regardless of organization
or process (D22). The generalized per-org template engine is deferred tech debt
(D21) and these enums must not grow toward it.

None of the four is ever assigned directly on a model instance. Every change
goes through PartDemandStateManager.transition(), which writes the journal row
and refreshes the snapshot column together.
"""

from django.db import models


class DemandState(models.TextChoices):
    """Is this need real, and authorized? Tracks the approval workflow. (D33)

    COMPLETED IS NO LONGER PART OF THE MANUAL WORKFLOW, but it is still a value
    on this axis and still the terminal state. Nobody transitions a demand into
    it by hand any more: it is written automatically when the parent graph's
    linear_status reaches DELIVERED and issuance_state is set to anything other
    than NOT_ISSUED — the material arrived AND it reached the person who asked
    for it. See DemandCompletionHandler.

    Once COMPLETED the demand is LOCKED and its state stops moving, even if the
    parent graph's linear_status later changes. A demand's fulfillment is a
    point-in-time fact — "I received X units on date Y and they went to the
    requester" — and unlike the graph, which merges, splits, and re-derives
    constantly, that fact should not rewrite itself.

    KNOWN, ACCEPTED DIVERGENCE: because the demand is frozen and the graph is
    not, a locked demand can read COMPLETED/DELIVERED while its parent graph
    reads something earlier — a merge brought in new members, or more material
    arrived. The alternative is either rewriting a completion record (which
    breaks the audit trail) or snapshotting the demand at completion time
    (a bigger change than this pass). Revisit if users report confusion about a
    demand looking finished while its graph needs attention.
    """

    PROJECTED = "projected", "Projected"
    REQUIRED = "required", "Required"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    CANCELLED = "cancelled", "Cancelled"
    # Automatic only — never a manual transition target. See the class
    # docstring for the locking rule and the divergence it accepts.
    COMPLETED = "completed", "Completed"


class PurchasingState(models.TextChoices):
    """Has money been authorized to move for this demand? (D34)

    The stored default is "" (blank), not a member of this enum — blank is a
    real, meaningful value meaning "no purchasing decision has been made yet",
    not missing data. There is deliberately no ``Manufactured Onsite`` value:
    in-house fabrication is an ordinary PO against an internal vendor.
    """

    APPROVED = "approved", "Approved"
    DENIED = "denied", "Denied"
    PURCHASED = "purchased", "Purchased"
    CANCELLED = "cancelled", "Cancelled"


#: The stored value of an unset ``purchasing_state``. A blank CharField rather
#: than NULL so the column, the journal's ``stage``/``previous_stage`` columns,
#: and every transition dict all speak the same type.
PURCHASING_STATE_UNSET = ""


class ShipmentState(models.TextChoices):
    """Where is the material physically, in transit? (D35)

    This build drives the chain up through Shipped/Backordered/Lost from
    PurchaseOrder.status and Shipment.status (D40), plus an explicit close-out at
    DELIVERED_TO_LOCAL. IN_STOCK is an enum surface for the later Inventory
    build and is never written here.
    """

    REQUEST_NOT_SENT = "request_not_sent", "Request Not Sent"
    REQUEST_RECEIVED_BY_VENDOR = "request_received_by_vendor", "Request Received by Vendor"
    PRODUCTION_IN_PROGRESS = "production_in_progress", "Production in Progress"
    VENDOR_PREPARED_TO_SHIP = "vendor_prepared_to_ship", "Vendor Prepared to Ship"
    SHIPPED = "shipped", "Shipped"
    BACKORDERED = "backordered", "Backordered"
    LOST = "lost", "Lost"
    DELIVERED_TO_DEPOT = "delivered_to_depot", "Delivered to Depot"
    DELIVERED_TO_LOCAL = "delivered_to_local", "Delivered to Local Receiving Location"
    IN_STOCK = "in_stock", "In Stock"


class IssuanceState(models.TextChoices):
    """Has the material been physically handed to the requester? (D36)

    ISSUED_PENDING_RECONCILIATION is the active borrow/return state: issued_qty
    reflects the full amount currently out, and returning nets it down via a
    second negative PartIssue row (D39). The Issued <-> Pending Reconciliation
    mechanics are owned by the later Inventory build; the surface exists here.

    ISSUED_RECONCILIATION_REQUIRED (D77) is a DIFFERENT question than the
    ISSUED_PENDING_RECONCILIATION state above: that one is "this is out and
    expected back" (an active loan). This one is "a physical movement already
    happened and the inventory system has not recorded it yet" — the books are
    behind reality. Deliberately a distinct value rather than an overload of
    the existing one, because a later Inventory kit needs to tell them apart.

    ISSUED_WITHOUT_STOCK_ADJUSTMENT indicates a technician acquired the part
    outside the formal inventory process — tracked but no stock movement recorded yet.
    """

    NOT_ISSUED = "not_issued", "Not Issued"
    PARTIALLY_ISSUED = "partially_issued", "Partially Issued"
    ISSUED = "issued", "Issued"
    ISSUED_WITHOUT_STOCK_ADJUSTMENT = (
        "issued_without_stock_adjustment",
        "Issued Without Stock Adjustment",
    )
    ISSUED_PENDING_RECONCILIATION = (
        "issued_pending_reconciliation",
        "Issued Pending Reconciliation",
    )
    ISSUED_RECONCILIATION_REQUIRED = (
        "issued_reconciliation_required",
        "Part Issued — Inventory Reconciliation Required",
    )


class DemandDimension(models.TextChoices):
    """Which axis a PartDemandUpdate journal row describes."""

    DEMAND = "demand", "Demand"
    PURCHASING = "purchasing", "Purchasing"
    SHIPMENT = "shipment", "Shipment"
    ISSUANCE = "issuance", "Issuance"


class DemandPriority(models.TextChoices):
    """Intrinsic to the need (M4)."""

    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class DemandSourceModule(models.TextChoices):
    """Which app/module originated this demand (D38).

    A denormalized filter/display convenience only — never a source of truth for
    origin detail. That resolves through each consumer app's own link table.
    """

    MAINTENANCE = "maintenance", "Maintenance"
    DISPATCHING = "dispatching", "Dispatching"
    GENERAL = "general", "General"


#: Maps a dimension to the PartDemand column it snapshots. Used by
#: PartDemandStateManager so the axis name appears exactly once in code.
DIMENSION_FIELDS: dict[str, str] = {
    DemandDimension.DEMAND: "demand_state",
    DemandDimension.PURCHASING: "purchasing_state",
    DemandDimension.SHIPMENT: "shipment_state",
    DemandDimension.ISSUANCE: "issuance_state",
}

#: Valid stage values per dimension, for journal validation.
DIMENSION_CHOICES: dict[str, frozenset[str]] = {
    DemandDimension.DEMAND: frozenset(DemandState.values),
    DemandDimension.PURCHASING: frozenset(PurchasingState.values) | {PURCHASING_STATE_UNSET},
    DemandDimension.SHIPMENT: frozenset(ShipmentState.values),
    DemandDimension.ISSUANCE: frozenset(IssuanceState.values),
}
