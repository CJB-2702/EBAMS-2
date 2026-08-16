"""Struct: the aggregated read for one Shipment — detail and edit both use it.

--------------------------------------------------------------------------
THE ATTRIBUTION RULE AGAIN, FROM THE SHIPMENT SIDE (D55).
--------------------------------------------------------------------------

PurchaseOrderFulfillmentStruct answers "how much of this ORDER arrived" and
refuses to divide a shared session among its members. This struct answers the
same question one step downstream — "who is this ARRIVING LINE for" — and it
refuses in exactly the same way, for the same reason.

Since D90 an arriving line may carry SEVERAL allocations, so attribution is
computed per ALLOCATION rather than per line: each allocation names one PO line,
and that PO line's active demand links decide what can honestly be said about
that slice of the box. A line with two allocations therefore shows two
attribution rows, which is the honest rendering — the alternative, one merged
attribution for the whole line, would have to blend two unrelated demand
populations into a single cell.

Per allocation, by the target PO line's count of active demand links:

  0    unlinked        Blank. Nobody claims it. Proactive stock, a substitution,
                       or a shipment that has no PO attached yet (D71/D73).
  1    attributable    The demand reference. A real 1:1:1 chain: this line, that
                       PO line, that demand.
  >=2  shared session  The member list and the session totals. NO PER-LINE
                       PER-DEMAND FIGURE IS PRODUCED, not even labelled as an
                       estimate — the units in the box are fungible and nobody
                       at the vendor decided whose they were.

The per-demand field is ABSENT on the shared branch rather than null, so a
caller cannot default it to zero and render a lie.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from app.procurement.control_layer.domain_structs.arrival_allocation import (
    accepted_by_purchase_order_line,
)
from app.procurement.models import (
    Shipment,
    ShipmentLine,
    PurchaseOrderDemandLink,
    PurchaseOrderShipmentLink,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)

ATTRIBUTION_UNLINKED = "unlinked"
ATTRIBUTION_ATTRIBUTABLE = "attributable"
ATTRIBUTION_SHARED_SESSION = "shared_session"


@dataclass(frozen=True)
class LineAttribution:
    """The "Attributed to" column's whole payload (phase_3 §3.5).

    One class with a mode discriminator rather than three, because unlike the
    fulfillment struct this is read straight into a template cell — and a
    Django template cannot do an isinstance check. The invariant is preserved
    by construction instead: `demand_id` is only ever set on the attributable
    branch, and `session_members` only on the shared branch.
    """

    mode: str = ATTRIBUTION_UNLINKED
    #: Attributable branch only.
    demand_id: int | None = None
    demand_domain_id: int | None = None
    demand_part_number: str = ""
    #: Shared-session branch only. (demand_id, domain_id, quantity_allocated).
    session_members: tuple[tuple[int, int, Decimal], ...] = ()
    session_allocated: Decimal = Decimal("0")
    session_arrived: Decimal = Decimal("0")

    @property
    def member_count(self) -> int:
        return len(self.session_members)


@dataclass(frozen=True)
class ShipmentLineAllocationSlice:
    """One allocation of an arriving line to a PO line (D90).

    Carries its own attribution because attribution is a property of the TARGET
    PO line's demand links, and one arriving line's allocations can land on PO
    lines with entirely different demand populations.
    """

    link_id: int
    quantity_allocated: Decimal
    purchase_order_line_id: int
    purchase_order_id: int | None
    purchase_order_domain_id: int | None
    po_number: str
    po_line_number: int | None
    #: True when this allocation points at a line on a PO other than the
    #: header's — the per-allocation half of the mixed_po_assignments flag.
    is_drifted: bool
    attribution: LineAttribution


@dataclass(frozen=True)
class ShipmentLineSlice:
    """One arriving line, flattened for display and for the allocation tool."""

    line_id: int
    part_id: int
    part_number: str
    part_name: str
    quantity: Decimal
    #: None means UNINSPECTED. Zero means inspected and everything rejected.
    #: These are different facts and the template must not collapse them.
    quantity_accepted: Decimal | None
    rejection_notes: str

    allocations: tuple[ShipmentLineAllocationSlice, ...] = ()
    quantity_allocated: Decimal = Decimal("0")

    @property
    def is_inspected(self) -> bool:
        return self.quantity_accepted is not None

    @property
    def unallocated_quantity(self) -> Decimal:
        """What arrived that no order line claims yet. A REAL STATE, not a
        discrepancy — the allocation guard caps the sum at `quantity`, so this
        is never negative."""
        remainder = self.quantity - self.quantity_allocated
        return remainder if remainder > 0 else Decimal("0")

    @property
    def is_fully_allocated(self) -> bool:
        return self.unallocated_quantity == 0

    @property
    def is_assigned(self) -> bool:
        """Any allocation at all. Distinct from is_fully_allocated: a partly
        allocated line is assigned AND still owes a remainder."""
        return bool(self.allocations)

    @property
    def is_drifted(self) -> bool:
        return any(allocation.is_drifted for allocation in self.allocations)


@dataclass(frozen=True)
class ShipmentDetailStruct:
    shipment_id: int
    shipment_number: str
    status: str
    domain_id: int
    purchase_order_id: int | None
    purchase_order_domain_id: int | None
    po_number: str
    vendor_name: str
    mixed_po_assignments: bool
    event_id: int | None

    lines: tuple[ShipmentLineSlice, ...] = ()
    total_shipped: Decimal = Decimal("0")
    total_accepted: Decimal = Decimal("0")

    @property
    def drifted_lines(self) -> tuple[ShipmentLineSlice, ...]:
        """The lines the mixed-assignment banner has to name. The flag alone
        says "something diverged"; a banner that cannot say WHAT is noise."""
        return tuple(line for line in self.lines if line.is_drifted)

    @property
    def unassigned_lines(self) -> tuple[ShipmentLineSlice, ...]:
        """Lines still owing an unallocated remainder — fully OR partially
        (D90). A line 80%-allocated is on this list, because the other 20% is
        exactly what would otherwise go unnoticed."""
        return tuple(line for line in self.lines if not line.is_fully_allocated)

    @classmethod
    def load(cls, *, shipment_id: int) -> "ShipmentDetailStruct":
        shipment = Shipment.objects.select_related(
            "purchase_order", "purchase_order__vendor", "domain"
        ).get(pk=shipment_id)

        lines = list(
            ShipmentLine.objects.filter(shipment=shipment, deleted_at__isnull=True)
            .select_related("part")
            .order_by("pk")
        )

        # One query for every allocation on this shipment, grouped in Python —
        # never a query per line, and never annotated alongside anything else
        # multi-row (the D67 fan-out).
        links_by_shipment_line: dict[int, list[PurchaseOrderShipmentLink]] = {}
        for link in PurchaseOrderShipmentLink.objects.filter(
            shipment_line__shipment=shipment,
            shipment_line__deleted_at__isnull=True,
            deleted_at__isnull=True,
        ).select_related("purchase_order_line", "purchase_order_line__purchase_order"):
            links_by_shipment_line.setdefault(link.shipment_line_id, []).append(link)

        attribution_by_po_line = cls._attribution_by_po_line(
            po_line_ids={
                link.purchase_order_line_id
                for links in links_by_shipment_line.values()
                for link in links
            }
        )

        slices: list[ShipmentLineSlice] = []
        total_shipped = Decimal("0")
        total_accepted = Decimal("0")
        for line in lines:
            total_shipped += line.quantity
            if line.quantity_accepted is not None:
                total_accepted += line.quantity_accepted

            allocations: list[ShipmentLineAllocationSlice] = []
            allocated = Decimal("0")
            for link in links_by_shipment_line.get(line.pk, []):
                po_line = link.purchase_order_line
                po = po_line.purchase_order
                allocated += link.quantity_allocated
                allocations.append(
                    ShipmentLineAllocationSlice(
                        link_id=link.pk,
                        quantity_allocated=link.quantity_allocated,
                        purchase_order_line_id=po_line.pk,
                        purchase_order_id=po.pk,
                        purchase_order_domain_id=po.domain_id,
                        po_number=po.po_number,
                        po_line_number=po_line.line_number,
                        is_drifted=(
                            shipment.purchase_order_id is not None
                            and po.pk != shipment.purchase_order_id
                        ),
                        attribution=attribution_by_po_line.get(
                            po_line.pk, LineAttribution()
                        ),
                    )
                )

            slices.append(
                ShipmentLineSlice(
                    line_id=line.pk,
                    part_id=line.part_id,
                    part_number=line.part.part_number,
                    part_name=line.part.name,
                    quantity=line.quantity,
                    quantity_accepted=line.quantity_accepted,
                    rejection_notes=line.rejection_notes,
                    allocations=tuple(allocations),
                    quantity_allocated=allocated,
                )
            )

        po = shipment.purchase_order
        return cls(
            shipment_id=shipment.pk,
            shipment_number=shipment.shipment_number,
            status=shipment.status,
            domain_id=shipment.domain_id,
            purchase_order_id=po.pk if po else None,
            purchase_order_domain_id=po.domain_id if po else None,
            po_number=po.po_number if po else "",
            vendor_name=po.vendor.name if po and po.vendor_id else "",
            mixed_po_assignments=shipment.mixed_po_assignments,
            event_id=shipment.event_id,
            lines=tuple(slices),
            total_shipped=total_shipped,
            total_accepted=total_accepted,
        )

    @staticmethod
    def _attribution_by_po_line(*, po_line_ids) -> dict[int, LineAttribution]:
        """One query for every active demand link behind the PO lines this
        shipment allocates to, and one for the session arrival totals — never a
        query per line."""
        po_line_ids = set(po_line_ids)
        if not po_line_ids:
            return {}

        links_by_line: dict[int, list[PurchaseOrderDemandLink]] = {}
        for link in PurchaseOrderDemandLink.objects.filter(
            purchase_order_line_id__in=po_line_ids,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("part_demand", "part_demand__part"):
            links_by_line.setdefault(link.purchase_order_line_id, []).append(link)

        # session_arrived is the accepted quantity across EVERY shipment
        # touching the line, not just this one — the session is a property of
        # the PO line, and reporting only this shipment's share would
        # understate it. Derived by allocation share since D90; see
        # arrival_allocation.py for why that division is admissible here.
        arrived_by_line = accepted_by_purchase_order_line(
            purchase_order_line_ids=po_line_ids
        )

        result: dict[int, LineAttribution] = {}
        for po_line_id in po_line_ids:
            links = links_by_line.get(po_line_id, [])
            if not links:
                result[po_line_id] = LineAttribution(mode=ATTRIBUTION_UNLINKED)
            elif len(links) == 1:
                link = links[0]
                result[po_line_id] = LineAttribution(
                    mode=ATTRIBUTION_ATTRIBUTABLE,
                    demand_id=link.part_demand_id,
                    demand_domain_id=link.part_demand.domain_id,
                    demand_part_number=link.part_demand.part.part_number,
                )
            else:
                result[po_line_id] = LineAttribution(
                    mode=ATTRIBUTION_SHARED_SESSION,
                    session_members=tuple(
                        sorted(
                            (
                                link.part_demand_id,
                                link.part_demand.domain_id,
                                link.quantity_allocated,
                            )
                            for link in links
                        )
                    ),
                    session_allocated=sum(
                        (link.quantity_allocated for link in links), Decimal("0")
                    ),
                    session_arrived=arrived_by_line.get(po_line_id, Decimal("0")),
                )
        return result


@dataclass(frozen=True)
class ShipmentPlanningLine:
    """One PO line as the Basic Shipment Manager's draggable chip.

    `already_shipped` counts EVERY shipment on the order, including the locked
    ones (D69), because a Buyer who cannot see the boxes they are not allowed
    to edit will happily plan the same units twice.
    """

    line_id: int
    line_number: int
    part_id: int
    part_number: str
    part_name: str
    qty_ordered: Decimal
    qty_already_shipped: Decimal

    @property
    def qty_remaining(self) -> Decimal:
        remaining = self.qty_ordered - self.qty_already_shipped
        return remaining if remaining > 0 else Decimal("0")

    @property
    def is_over_shipped(self) -> bool:
        """Legal — vendors over-ship and Buyers plan for it — but worth
        surfacing (D13: report, never block)."""
        return self.qty_already_shipped > self.qty_ordered


def planning_lines_for_order(*, purchase_order) -> tuple[ShipmentPlanningLine, ...]:
    """The Basic Shipment Manager's left column, in one query."""
    from app.procurement.models import PurchaseOrderLine

    rows = (
        PurchaseOrderLine.objects.filter(
            purchase_order=purchase_order, deleted_at__isnull=True
        )
        .select_related("part")
        .annotate(
            # Allocated, not shipped-line quantity (D90). The two used to be
            # the same number because a whole arriving line pointed at one PO
            # line; now only the allocated share counts against this order.
            # EXACT — no proration is involved on the shipped side.
            shipped_total=Coalesce(
                Subquery(
                    PurchaseOrderShipmentLink.objects.filter(
                        purchase_order_line=OuterRef("pk"),
                        deleted_at__isnull=True,
                        shipment_line__deleted_at__isnull=True,
                    )
                    .values("purchase_order_line")
                    .annotate(total=Sum("quantity_allocated"))
                    .values("total")[:1],
                    output_field=_DECIMAL,
                ),
                Decimal("0"),
                output_field=_DECIMAL,
            )
        )
        .order_by("line_number")
    )
    return tuple(
        ShipmentPlanningLine(
            line_id=row.pk,
            line_number=row.line_number,
            part_id=row.part_id,
            part_number=row.part.part_number,
            part_name=row.part.name,
            qty_ordered=row.quantity_ordered,
            qty_already_shipped=row.shipped_total,
        )
        for row in rows
    )
