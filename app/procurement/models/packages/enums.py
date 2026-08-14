"""Package shipment-tracking status.

Package.status is what drives PartDemand.shipment_state on the demands behind
a package's lines — the role D35/D40 always intended for it.

ACCEPTED is the package-level counterpart of the Buyer's close-out. It does
NOT mean stocked: stocked is intake's word, and intake is not built.
"""

from django.db import models


class PackageStatus(models.TextChoices):
    AWAITING_SHIPMENT = "awaiting_shipment", "Awaiting Shipment"
    BACKORDERED = "backordered", "Backordered"
    SHIPPED = "shipped", "Shipped"
    DELIVERED_TO_DEPOT = "delivered_to_depot", "Delivered to Depot"
    DELIVERED_TO_LOCAL = "delivered_to_local", "Delivered to Local Receiving Location"
    ACCEPTED = "accepted", "Accepted"
    LOST = "lost", "Lost"
    # Terminal, reachable from any non-terminal state — same shape as
    # PurchaseOrderApprovalState's Cancelled (Denied/Cancelled reachable from
    # either non-terminal state, any time).
    CANCELLED = "cancelled", "Cancelled"
