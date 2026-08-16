"""Struct: the four quantities, per-line attribution mode, and shipment rollups.

Since shipments live in procurement (D59/D60) this is an ordinary within-app
read. It was previously specced as a cross-app `# DELIBERATE ANTI-PATTERN`
reading inventory; moving Shipment/ShipmentLine into this app removed the need
for the exception entirely.

--------------------------------------------------------------------------
THE ATTRIBUTION RULE (D55). Read shared_demand_sessions.md before changing it.
--------------------------------------------------------------------------

"How much of my demand arrived?" is the most common question business asks of
this system, and for a large fraction of demands IT IS NOT ANSWERABLE — not
because data is missing, but because the fact does not exist.

A line buys 100 units. Three demands are allocated: 50, 30, 20. A shipment
arrives with 60 accepted units. Which demand got them? There is no answer. The
units are fungible, nobody at the vendor decided whose they were, and every
available invention is worse than silence:

  - proportional split (30/18/12) is arithmetic dressed as fact, wrong the
    moment a receiver hands all 60 to whoever needed them first;
  - first-come attribution is a policy guess the system was never told;
  - asking a human at receipt collects a guess and launders it into the audit
    trail as though it were observed.

So per PO line, by its count of ACTIVE demand links:

  0    unlinked        Proactive stock. The arrival is real; no demand claims it.
  1    attributable    qty_arrived_for_demand — a real per-demand number.
  >=2  shared_session  session_allocated, session_arrived, session_members.
                       NO PER-DEMAND FIGURE IS PRODUCED AT ALL.

THE SYSTEM MUST NEVER DIVIDE session_arrived AMONG MEMBERS. Not in a struct,
not in a report, not in a tooltip, not as an "estimate."

The per-demand field is ABSENT, NOT NULL, on the shared branch — that is why
the three modes are three separate classes rather than one class with optional
fields. A field that is sometimes a number and sometimes null invites a caller
to default it to zero and report a lie; a field that does not exist forces the
caller to handle the case.

The remedy for a business that genuinely needs per-demand tracking is a Buyer
action, not a formula: GIVE EACH DEMAND ITS OWN PO LINE. That trade belongs to
the Buyer on the specific order, not to a system-wide policy.

WHERE qty_from_accepted_shipments COMES FROM NOW (D90). It used to be a plain
sum of ShipmentLine.quantity_accepted over the lines whose FK pointed here.
Shipment lines no longer carry that FK — they carry allocations — so the number
is derived by allocation share in arrival_allocation.py. That module is the ONLY
place in this app where a quantity is divided, and its docstring explains why
the division is admissible there and remains forbidden on the demand side above.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from app.procurement.control_layer.domain_structs.arrival_allocation import (
    accepted_by_purchase_order_line,
    allocated_by_shipment_line,
)
from app.procurement.models import (
    Shipment,
    ShipmentLine,
    PartDemand,
    PurchaseOrder,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)

ATTRIBUTION_UNLINKED = "unlinked"
ATTRIBUTION_ATTRIBUTABLE = "attributable"
ATTRIBUTION_SHARED_SESSION = "shared_session"


@dataclass(frozen=True)
class _LineQuantities:
    """The four quantities, no overloaded word among them."""

    line_id: int
    line_number: int
    part_id: int
    part_number: str
    qty_ordered: Decimal
    qty_allocated: Decimal
    qty_from_accepted_shipments: Decimal
    qty_issued: Decimal

    @property
    def over_received(self) -> bool:
        """Legal — vendors over-ship — but flagged for visibility (D13: report,
        never block)."""
        return self.qty_from_accepted_shipments > self.qty_ordered


@dataclass(frozen=True)
class UnlinkedLineFulfillment(_LineQuantities):
    attribution_mode: str = ATTRIBUTION_UNLINKED


@dataclass(frozen=True)
class AttributableLineFulfillment(_LineQuantities):
    """Exactly one active demand link: a real, reportable per-demand number."""

    demand_id: int = 0
    qty_arrived_for_demand: Decimal = Decimal("0")
    attribution_mode: str = ATTRIBUTION_ATTRIBUTABLE


@dataclass(frozen=True)
class SharedSessionLineFulfillment(_LineQuantities):
    """Two or more active demand links.

    Note what is NOT on this class: there is no per-demand arrival field. Read
    as "this demand is in a shared session of 100 across 3 demands, of which 60
    have arrived." That sentence is longer than a single number and it is the
    honest one.
    """

    session_allocated: Decimal = Decimal("0")
    session_arrived: Decimal = Decimal("0")
    session_members: tuple[int, ...] = ()
    attribution_mode: str = ATTRIBUTION_SHARED_SESSION

    @property
    def member_count(self) -> int:
        return len(self.session_members)


@dataclass(frozen=True)
class ShipmentRollup:
    """Answers the manager's direct question: how many items came in for this
    shipment."""

    shipment_id: int
    shipment_number: str
    status: str
    line_count: int
    total_shipped: Decimal
    total_accepted: Decimal
    mixed_po_assignments: bool


@dataclass(frozen=True)
class PurchaseOrderFulfillmentStruct:
    purchase_order_id: int
    po_number: str
    status: str
    lines: tuple[_LineQuantities, ...] = ()
    shipments: tuple[ShipmentRollup, ...] = ()
    #: Arrived with some quantity not yet pointed at any PO line — fully OR
    #: partially unallocated (D90). Surfaced, never dropped.
    unassigned_shipment_line_ids: tuple[int, ...] = ()

    @classmethod
    def load(cls, *, purchase_order_id: int) -> "PurchaseOrderFulfillmentStruct":
        po = PurchaseOrder.objects.get(pk=purchase_order_id)

        lines = (
            PurchaseOrderLine.objects.filter(
                purchase_order=po, deleted_at__isnull=True
            )
            .select_related("part")
            .annotate(
                allocated_total=Coalesce(
                    Sum(
                        "allocations__quantity_allocated",
                        filter=Q(
                            allocations__is_active=True,
                            allocations__deleted_at__isnull=True,
                        ),
                    ),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
                active_link_count=Count(
                    "allocations",
                    filter=Q(
                        allocations__is_active=True,
                        allocations__deleted_at__isnull=True,
                    ),
                    distinct=True,
                ),
            )
            .order_by("line_number")
        )

        # Arrival is NOT annotated onto the queryset above (D90). It used to be
        # a correlated subquery over shipment_lines, which itself replaced a
        # joined Sum() that fanned out against `allocations` and double-counted
        # every accepted quantity once per demand link (D67). Now that arrival
        # derives from allocation shares rather than a single FK, it is a plain
        # dict built by one dedicated helper — the fan-out class of bug cannot
        # occur because no second multi-row relation is ever joined here.
        line_ids = [line.pk for line in lines]
        accepted_by_line = accepted_by_purchase_order_line(
            purchase_order_line_ids=line_ids
        )

        # One query for every active link on this PO, grouped in Python — not
        # a query per line.
        links_by_line: dict[int, list[PurchaseOrderDemandLink]] = {}
        for link in PurchaseOrderDemandLink.objects.filter(
            purchase_order_line__purchase_order=po,
            is_active=True,
            deleted_at__isnull=True,
        ):
            links_by_line.setdefault(link.purchase_order_line_id, []).append(link)

        demand_ids = {
            link.part_demand_id
            for links in links_by_line.values()
            for link in links
        }
        issued_by_demand = dict(
            PartDemand.objects.filter(pk__in=demand_ids).values_list(
                "pk", "issued_qty"
            )
        )

        line_structs: list[_LineQuantities] = []
        for line in lines:
            links = links_by_line.get(line.pk, [])
            accepted_total = accepted_by_line.get(line.pk, Decimal("0"))
            qty_issued = sum(
                (issued_by_demand.get(link.part_demand_id, Decimal("0")) for link in links),
                Decimal("0"),
            )
            common = {
                "line_id": line.pk,
                "line_number": line.line_number,
                "part_id": line.part_id,
                "part_number": line.part.part_number,
                "qty_ordered": line.quantity_ordered,
                "qty_allocated": line.allocated_total,
                "qty_from_accepted_shipments": accepted_total,
                # Deliberately a rollup of the DEMAND side, not an inventory
                # number: it answers "has this order's material reached
                # anyone", which is the manager's real question, and it comes
                # from a column this app already owns.
                "qty_issued": qty_issued,
            }

            if not links:
                line_structs.append(UnlinkedLineFulfillment(**common))
            elif len(links) == 1:
                line_structs.append(
                    AttributableLineFulfillment(
                        **common,
                        demand_id=links[0].part_demand_id,
                        qty_arrived_for_demand=accepted_total,
                    )
                )
            else:
                line_structs.append(
                    SharedSessionLineFulfillment(
                        **common,
                        session_allocated=line.allocated_total,
                        session_arrived=accepted_total,
                        session_members=tuple(
                            sorted(link.part_demand_id for link in links)
                        ),
                    )
                )

        shipments = tuple(
            ShipmentRollup(
                shipment_id=pkg.pk,
                shipment_number=pkg.shipment_number,
                status=pkg.status,
                line_count=pkg.line_count,
                total_shipped=pkg.shipped_total,
                total_accepted=pkg.accepted_total,
                mixed_po_assignments=pkg.mixed_po_assignments,
            )
            for pkg in Shipment.objects.filter(
                purchase_order=po, deleted_at__isnull=True
            ).annotate(
                line_count=Count(
                    "lines", filter=Q(lines__deleted_at__isnull=True), distinct=True
                ),
                shipped_total=Coalesce(
                    Sum("lines__quantity", filter=Q(lines__deleted_at__isnull=True)),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
                accepted_total=Coalesce(
                    Sum(
                        "lines__quantity_accepted",
                        filter=Q(lines__deleted_at__isnull=True),
                    ),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
            )
        )

        # PARTIALLY allocated counts as unassigned here (D90). Under the old
        # single-FK design a line was assigned or it was not; now a line can be
        # 80 of 100 pointed at an order and 20 still floating, and the 20 is
        # exactly the thing this list exists to stop anyone from losing.
        arriving = list(
            ShipmentLine.objects.filter(
                shipment__purchase_order=po, deleted_at__isnull=True
            ).only("pk", "quantity")
        )
        allocated_per_line = allocated_by_shipment_line(
            shipment_line_ids=[line.pk for line in arriving]
        )
        unassigned = tuple(
            line.pk
            for line in arriving
            if allocated_per_line.get(line.pk, Decimal("0")) < line.quantity
        )

        return cls(
            purchase_order_id=po.pk,
            po_number=po.po_number,
            status=po.status,
            lines=tuple(line_structs),
            shipments=shipments,
            unassigned_shipment_line_ids=unassigned,
        )

    def to_dict(self) -> dict:
        return {
            "purchase_order_id": self.purchase_order_id,
            "po_number": self.po_number,
            "status": self.status,
            "lines": [cls_to_dict(line) for line in self.lines],
            "shipments": [
                {
                    "shipment_id": p.shipment_id,
                    "shipment_number": p.shipment_number,
                    "status": p.status,
                    "line_count": p.line_count,
                    "total_shipped": p.total_shipped,
                    "total_accepted": p.total_accepted,
                    "mixed_po_assignments": p.mixed_po_assignments,
                }
                for p in self.shipments
            ],
            "unassigned_shipment_line_ids": list(self.unassigned_shipment_line_ids),
        }


def cls_to_dict(line: _LineQuantities) -> dict:
    """Serialize a line WITHOUT inventing fields its mode does not have.

    The shared-session branch emits no per-demand key at all — a caller that
    wants one must handle the mode.
    """
    base = {
        "line_id": line.line_id,
        "line_number": line.line_number,
        "part_id": line.part_id,
        "part_number": line.part_number,
        "qty_ordered": line.qty_ordered,
        "qty_allocated": line.qty_allocated,
        "qty_from_accepted_shipments": line.qty_from_accepted_shipments,
        "qty_issued": line.qty_issued,
        "attribution_mode": line.attribution_mode,
        "over_received": line.over_received,
    }
    if isinstance(line, AttributableLineFulfillment):
        base["demand_id"] = line.demand_id
        base["qty_arrived_for_demand"] = line.qty_arrived_for_demand
    elif isinstance(line, SharedSessionLineFulfillment):
        base["session_allocated"] = line.session_allocated
        base["session_arrived"] = line.session_arrived
        base["session_members"] = list(line.session_members)
        base["member_count"] = line.member_count
    return base
