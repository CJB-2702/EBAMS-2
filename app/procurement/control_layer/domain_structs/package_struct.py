"""Struct: the aggregated read for one Package — detail and edit both use it.

--------------------------------------------------------------------------
THE ATTRIBUTION RULE AGAIN, FROM THE PACKAGE SIDE (D55).
--------------------------------------------------------------------------

PurchaseOrderFulfillmentStruct answers "how much of this ORDER arrived" and
refuses to divide a shared session among its members. This struct answers the
same question one step downstream — "who is this ARRIVING LINE for" — and it
refuses in exactly the same way, for the same reason.

A package line points at one PO line. That PO line's active demand links decide
what can honestly be said:

  0    unlinked        Blank. Nobody claims it. Proactive stock, a substitution,
                       or a package that has no PO attached yet (D71/D73).
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

from django.db.models import Count, DecimalField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from app.procurement.models import (
    Package,
    PackageLine,
    PurchaseOrderDemandLink,
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
class PackageLineSlice:
    """One arriving line, flattened for display and for the assignment tool."""

    line_id: int
    part_id: int
    part_number: str
    part_name: str
    quantity: Decimal
    #: None means UNINSPECTED. Zero means inspected and everything rejected.
    #: These are different facts and the template must not collapse them.
    quantity_accepted: Decimal | None
    rejection_notes: str

    purchase_order_line_id: int | None
    purchase_order_id: int | None
    purchase_order_domain_id: int | None
    po_number: str
    po_line_number: int | None
    #: True when this line points at a line on a PO other than the header's —
    #: the per-line half of the mixed_po_assignments flag.
    is_drifted: bool

    split_from_id: int | None
    split_child_count: int

    attribution: LineAttribution

    @property
    def is_inspected(self) -> bool:
        return self.quantity_accepted is not None

    @property
    def is_assigned(self) -> bool:
        return self.purchase_order_line_id is not None


@dataclass(frozen=True)
class PackageDetailStruct:
    package_id: int
    package_number: str
    status: str
    domain_id: int
    purchase_order_id: int | None
    purchase_order_domain_id: int | None
    po_number: str
    vendor_name: str
    has_splits: bool
    mixed_po_assignments: bool
    event_id: int | None

    lines: tuple[PackageLineSlice, ...] = ()
    total_shipped: Decimal = Decimal("0")
    total_accepted: Decimal = Decimal("0")

    @property
    def drifted_lines(self) -> tuple[PackageLineSlice, ...]:
        """The lines the mixed-assignment banner has to name. The flag alone
        says "something diverged"; a banner that cannot say WHAT is noise."""
        return tuple(line for line in self.lines if line.is_drifted)

    @property
    def unassigned_lines(self) -> tuple[PackageLineSlice, ...]:
        return tuple(line for line in self.lines if not line.is_assigned)

    @classmethod
    def load(cls, *, package_id: int) -> "PackageDetailStruct":
        package = Package.objects.select_related(
            "purchase_order", "purchase_order__vendor", "domain"
        ).get(pk=package_id)

        lines = list(
            PackageLine.objects.filter(package=package, deleted_at__isnull=True)
            .select_related(
                "part",
                "purchase_order_line",
                "purchase_order_line__purchase_order",
            )
            .annotate(
                # A correlated subquery, not a joined Count: `splits` is a
                # second multi-row relation and counting it beside anything
                # else over `allocations` would fan out.
                split_children=Coalesce(
                    Subquery(
                        PackageLine.objects.filter(
                            split_from=OuterRef("pk"), deleted_at__isnull=True
                        )
                        .values("split_from")
                        .annotate(total=Count("pk"))
                        .values("total")[:1]
                    ),
                    0,
                )
            )
            .order_by("pk")
        )

        attribution_by_po_line = cls._attribution_by_po_line(lines)

        slices: list[PackageLineSlice] = []
        total_shipped = Decimal("0")
        total_accepted = Decimal("0")
        for line in lines:
            po_line = line.purchase_order_line
            po = po_line.purchase_order if po_line is not None else None
            total_shipped += line.quantity
            if line.quantity_accepted is not None:
                total_accepted += line.quantity_accepted

            slices.append(
                PackageLineSlice(
                    line_id=line.pk,
                    part_id=line.part_id,
                    part_number=line.part.part_number,
                    part_name=line.part.name,
                    quantity=line.quantity,
                    quantity_accepted=line.quantity_accepted,
                    rejection_notes=line.rejection_notes,
                    purchase_order_line_id=line.purchase_order_line_id,
                    purchase_order_id=po.pk if po else None,
                    purchase_order_domain_id=po.domain_id if po else None,
                    po_number=po.po_number if po else "",
                    po_line_number=po_line.line_number if po_line else None,
                    is_drifted=(
                        po is not None
                        and package.purchase_order_id is not None
                        and po.pk != package.purchase_order_id
                    ),
                    split_from_id=line.split_from_id,
                    split_child_count=line.split_children or 0,
                    attribution=attribution_by_po_line.get(
                        line.purchase_order_line_id, LineAttribution()
                    ),
                )
            )

        po = package.purchase_order
        return cls(
            package_id=package.pk,
            package_number=package.package_number,
            status=package.status,
            domain_id=package.domain_id,
            purchase_order_id=po.pk if po else None,
            purchase_order_domain_id=po.domain_id if po else None,
            po_number=po.po_number if po else "",
            vendor_name=po.vendor.name if po and po.vendor_id else "",
            has_splits=package.has_splits,
            mixed_po_assignments=package.mixed_po_assignments,
            event_id=package.event_id,
            lines=tuple(slices),
            total_shipped=total_shipped,
            total_accepted=total_accepted,
        )

    @staticmethod
    def _attribution_by_po_line(lines) -> dict[int, LineAttribution]:
        """One query for every active link behind this package's PO lines, and
        one for the session arrival totals — never a query per line."""
        po_line_ids = {
            line.purchase_order_line_id
            for line in lines
            if line.purchase_order_line_id is not None
        }
        if not po_line_ids:
            return {}

        links_by_line: dict[int, list[PurchaseOrderDemandLink]] = {}
        for link in PurchaseOrderDemandLink.objects.filter(
            purchase_order_line_id__in=po_line_ids,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("part_demand", "part_demand__part"):
            links_by_line.setdefault(link.purchase_order_line_id, []).append(link)

        # session_arrived is the accepted quantity across EVERY package touching
        # the line, not just this one — the session is a property of the PO
        # line, and reporting only this package's share would understate it.
        arrived_by_line = {
            row["purchase_order_line"]: row["total"] or Decimal("0")
            for row in PackageLine.objects.filter(
                purchase_order_line_id__in=po_line_ids, deleted_at__isnull=True
            )
            .values("purchase_order_line")
            .annotate(total=Sum("quantity_accepted", output_field=_DECIMAL))
        }

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
class PackagePlanningLine:
    """One PO line as the Basic Package Manager's draggable chip.

    `already_packaged` counts EVERY package on the order, including the locked
    ones (D69), because a Buyer who cannot see the boxes they are not allowed
    to edit will happily plan the same units twice.
    """

    line_id: int
    line_number: int
    part_id: int
    part_number: str
    part_name: str
    qty_ordered: Decimal
    qty_already_packaged: Decimal

    @property
    def qty_remaining(self) -> Decimal:
        remaining = self.qty_ordered - self.qty_already_packaged
        return remaining if remaining > 0 else Decimal("0")

    @property
    def is_over_packaged(self) -> bool:
        """Legal — vendors over-ship and Buyers plan for it — but worth
        surfacing (D13: report, never block)."""
        return self.qty_already_packaged > self.qty_ordered


def planning_lines_for_order(*, purchase_order) -> tuple[PackagePlanningLine, ...]:
    """The Basic Package Manager's left column, in one query."""
    from app.procurement.models import PurchaseOrderLine

    rows = (
        PurchaseOrderLine.objects.filter(
            purchase_order=purchase_order, deleted_at__isnull=True
        )
        .select_related("part")
        .annotate(
            packaged_total=Coalesce(
                Subquery(
                    PackageLine.objects.filter(
                        purchase_order_line=OuterRef("pk"), deleted_at__isnull=True
                    )
                    .values("purchase_order_line")
                    .annotate(total=Sum("quantity"))
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
        PackagePlanningLine(
            line_id=row.pk,
            line_number=row.line_number,
            part_id=row.part_id,
            part_number=row.part.part_number,
            part_name=row.part.name,
            qty_ordered=row.quantity_ordered,
            qty_already_packaged=row.packaged_total,
        )
        for row in rows
    )
