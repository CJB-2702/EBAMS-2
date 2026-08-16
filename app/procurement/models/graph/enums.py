"""GraphSummary's status axes.

THREE INDEPENDENT AXES, NOT ONE COMPOSITE (D9). Each answers a different
question and none of them writes another:

    LinearStatus              where in the end-to-end pipeline is this?
    POImbalanceState          are the demands committed to purchase orders?
    ShipmentImbalanceState    did we receive what we ordered?

Each is derived by a PRECEDENCE CHAIN — evaluated top to bottom, first match
wins — never by an AND/OR combination. AND produces a nearly empty result set;
OR puts a graph in three states at once with no way to filter. Precedence gives
every graph exactly one value per axis.

An earlier design used a single precedence-ordered `GraphImbalance` enum with
values like UNATTACHED / OVER_DELIVERED / UNDER_ALLOCATED / AWAITING_PLACEMENT.
It was rejected (D9) because it conflated two unrelated questions — commitment
gaps versus delivery gaps — and any precedence order it chose would favour one
reader's workflow over another's. A Buyer needs allocation clarity; a receiving
administrator needs delivery clarity; neither should read the other's logic.

The reference document for all of this is
`demand_graph_surfaces_starter_kit/all_statuses_review.md`, which is the
authority for status shape across PartDemand and GraphSummary.

Every value below is written exclusively by GraphSummaryManager.recalculate(),
never assigned by a caller — with the deliberate exception of
GraphResolutionState and its two companion columns, documented on the model.
"""

from django.db import models


class GraphSummaryStatus(models.TextChoices):
    """The original plain glanceable label (D81/D86).

    Kept because existing narrators, structs, and the graph detail template all
    read it. Superseded in intent by LinearStatus below, which answers the same
    "where is this" question against the allocation-based quantities rather
    than the ordered-based ones. Do not add values here; add them to
    LinearStatus.
    """

    # Nothing outstanding on any axis the graph currently uses.
    BALANCED = "balanced", "Balanced"
    # Demand exists with nothing yet purchased against it.
    AWAITING_PURCHASE = "awaiting_purchase", "Awaiting Purchase"
    # Purchased, nothing shipped/delivered yet.
    AWAITING_SHIPMENT = "awaiting_shipment", "Awaiting Shipment"
    # Delivered, nothing accepted/rejected yet.
    AWAITING_ACCEPTANCE = "awaiting_acceptance", "Awaiting Acceptance"


class LinearStatus(models.TextChoices):
    """Where in the end-to-end pipeline is this graph? (all_statuses_review §3)

    The one status a non-procurement reader can understand without knowing what
    an allocation is. Shared downward: each member PartDemand carries a copy of
    its parent graph's value, so a demand list can show pipeline position
    without joining to the graph.

    Precedence, first match wins:
      UNLINKED                    po_qty_allocated == 0 AND shipment_qty_allocated == 0
      PO_ALLOCATED_NOT_PURCHASED  po_qty_allocated > 0 AND po_qty_purchased == 0
      PO_PURCHASED_NOT_SHIPPED    po_qty_purchased > 0 AND shipment_qty_accepted == 0
      PARTIALLY_DELIVERED         0 < shipment_qty_accepted < demand_qty
      DELIVERED                   shipment_qty_accepted >= demand_qty
    """

    UNLINKED = "unlinked", "Unlinked"
    PO_ALLOCATED_NOT_PURCHASED = (
        "po_allocated_not_purchased",
        "Allocated, Not Purchased",
    )
    PO_PURCHASED_NOT_SHIPPED = (
        "po_purchased_not_shipped",
        "Purchased, Awaiting Delivery",
    )
    PARTIALLY_DELIVERED = "partially_delivered", "Partially Delivered"
    DELIVERED = "delivered", "Delivered"


class POImbalanceState(models.TextChoices):
    """PO side: are the demands fully committed to purchase orders?

    Compares demand_qty against po_qty_allocated and po_qty_purchased.

    THE MEASURE IS ALLOCATION, NOT ORDERED QUANTITY, for the first two values.
    PurchaseOrderLine.quantity_ordered is how many units the line buys;
    PurchaseOrderDemandLink.quantity_allocated is how many of those are claimed
    as fulfilling a specific demand. A PO may exist with zero linked demands
    (D14) because that is how bulk restocking is modelled — a line ordering
    1000 widgets against a 10-unit demand is healthy, and an ordered-based
    "under/over" comparison would report it as over-ordered by 990.

    PO_QUANTITY_EXCEEDS_DEMAND deliberately DOES surface the overbuy case
    anyway (D10b/D25), as its own filterable value rather than mixed into a
    ranked list. It exists so an administrator can ask "what did we buy beyond
    what anyone requested" — a real purchasing question with no other answer in
    the system.

    EXPECT THIS TO BE THE LARGEST NON-BALANCED POPULATION IN THE TABLE. Every
    bulk restock produces one and nothing clears it automatically. That is
    correct and not a bug: this axis is descriptive, not a task list.

    Precedence, first match wins.
    """

    # Some demand has no PO commitment yet -> allocate, or raise a PO.
    DEMAND_EXCEEDS_ALLOCATION = (
        "demand_exceeds_allocation",
        "Demand Exceeds Allocation",
    )
    # Allocations exist but the orders were never placed -> place them.
    ALLOCATION_EXCEEDS_PURCHASED = (
        "allocation_exceeds_purchased",
        "Allocated, Order Not Placed",
    )
    # More was purchased than anyone demanded. Usually intentional restocking.
    PO_QUANTITY_EXCEEDS_DEMAND = (
        "po_quantity_exceeds_demand",
        "Purchased Exceeds Demand",
    )
    # Demand fully purchased with extra allocated on top. Healthy (D10).
    DEMAND_SATISFIED_EXCESS_ALLOCATED = (
        "demand_satisfied_excess_allocated",
        "Satisfied, Excess Allocated",
    )
    BALANCED = "balanced", "Balanced"


class ShipmentImbalanceState(models.TextChoices):
    """Shipment side: did we receive what we ordered?

    THE REFERENCE POINT IS po_qty_purchased, NOT demand_qty (D10). Shipments
    are arrivals against orders, not against demands. Whether the demand is
    covered is the PO axis's question; this axis only answers "did the material
    we ordered turn up". Tracking arrivals against demand instead would report
    a graph as under-delivered when the real problem is that nobody ordered
    enough — a PO-side fact, reported twice.

    OVER_DELIVERED is the genuine, common, unpreventable over-condition: a
    vendor ships 12 against an order for 10. Nothing guards it upstream, and
    per D12 it is usually the system learning a vendor fact late rather than
    anybody's mistake. Wording that surfaces it must never imply error.

    Precedence, first match wins.
    """

    # Orders placed, but no shipment line has been mapped to them yet.
    PO_ORDERED_NOT_ALLOCATED_TO_SHIPMENTS = (
        "po_ordered_not_allocated_to_shipments",
        "Ordered, Not Allocated to Shipments",
    )
    # More allocated to shipments than was ever ordered -> allocation mix-up.
    SHIPMENT_ALLOCATION_EXCEEDS_PO = (
        "shipment_allocation_exceeds_po",
        "Shipment Allocation Exceeds Order",
    )
    # More arrived than was ordered. The classic vendor overship.
    OVER_DELIVERED = "over_delivered", "Over-Delivered"
    # Some arrived, some still in flight.
    PARTIAL_DELIVERY_RECEIVED = (
        "partial_delivery_received",
        "Partial Delivery Received",
    )
    # Shipments are tracked but nothing has arrived yet.
    SHIPMENTS_ALLOCATED_AWAITING_DELIVERY = (
        "shipments_allocated_awaiting_delivery",
        "Awaiting Delivery",
    )
    BALANCED = "balanced", "Balanced"


class GraphResolutionState(models.TextChoices):
    """The human judgment column — has a person ruled on this graph?

    NOT DERIVED. This is one of the three columns on GraphSummary that
    recalculate() must never touch; see the model docstring.

    Separate from every axis above because a derived state answers "does the
    arithmetic currently balance", which flips back the instant anything
    changes, while this answers "did a human look at it and finish with it".
    Without it, a legitimately-permanently-imbalanced graph — the vendor
    overshipped 12 against a demand for 10, everything was accepted, the
    business is done — is immortal noise in every filtered list.

    ACCEPTED_AS_IS is distinct from RESOLVED because they mean different things
    to the next reader: "this got fixed" versus "this is permanently lopsided
    and that is fine".

    Cleared back to OPEN on merge and split (D14) — the statement was about a
    specific set of nodes, and when nodes join or leave, the thing that was
    looked at no longer exists.
    """

    OPEN = "open", "Open"
    RESOLVED = "resolved", "Resolved"
    ACCEPTED_AS_IS = "accepted_as_is", "Accepted As-Is"


#: Values meaning "this axis is at rest". A graph's *condition* (the collective
#: "does this need a human?" reading) is any axis away from its resting value.
#: Not a stored column — a filter definition, used by the by-domain rollup and
#: by any caller wanting the whole non-balanced population in one predicate.
RESTING_VALUES: dict[str, str] = {
    "po_imbalance_state": POImbalanceState.BALANCED,
    "shipment_imbalance_state": ShipmentImbalanceState.BALANCED,
    "linear_status": LinearStatus.DELIVERED,
}
