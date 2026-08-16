"""Search: the allocation tool's PO lookup.

THIS IS THE TOOL'S REAL WORK. Finding the right line across a vendor's open
orders is the hard part, not the arithmetic — which is why pointing arrived
material at an order line gets a search surface at all rather than a plain
dropdown. (It served the splitting wizard before D90; the wizard is gone, the
lookup problem is not.)
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce

from app.procurement.models import (
    PurchaseOrderLine,
    PurchaseOrderShipmentLink,
    PurchaseOrderStatus,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)

#: Orders a vendor could still be shipping against.
OPEN_PURCHASE_ORDER_STATUSES = frozenset(
    {
        PurchaseOrderStatus.PLACED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
    }
)


class PurchaseOrderLineSearch:
    @classmethod
    def _annotate_arrival_facts(cls, qs: QuerySet) -> QuerySet:
        """The three numbers a receiver judges a candidate line by: how much was
        ordered, how much arrived material is already allocated against it, and
        the outstanding balance.

        Shared by the part-scoped candidate lookup and the wizard's cross-part
        pool so the two can never disagree about what "outstanding" means.
        """
        return qs.annotate(
            # ALLOCATED, not accepted (D90). The question this tool is
            # answering is "how much of this order line is still waiting to
            # be pointed at arrived material" — an allocation answers that
            # the moment it is made, well before anyone inspects. Accepted
            # quantity is the wrong basis here and would show every line as
            # wide open until inspection happened.
            #
            # A correlated subquery, not a joined Sum: annotating a Sum over
            # the links alongside the allocations Count below would fan out
            # and multiply the total by the number of demand allocations.
            qty_allocated_from_shipments=Coalesce(
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
            ),
            active_allocation_count=Count(
                "allocations",
                filter=Q(
                    allocations__is_active=True,
                    allocations__deleted_at__isnull=True,
                ),
                distinct=True,
            ),
        ).annotate(
            # quantity_ordered is a per-row field — subtract directly
            # rather than aggregating it across a join.
            outstanding_qty=F("quantity_ordered") - F("qty_allocated_from_shipments"),
        )

    @classmethod
    def pool(
        cls,
        *,
        domain_ids,
        q: str = "",
        vendor_id: int | None = None,
        purchase_order_id: int | None = None,
        include_draft: bool = False,
        outstanding_only: bool = True,
    ) -> QuerySet[PurchaseOrderLine]:
        """The create-shipment wizard's cross-part pool of order lines.

        The exact counterpart of `OpenDemandSearch.pool` one level up the chain:
        the PO wizard searches open DEMANDS to turn into order lines, and this
        searches open ORDER LINES to turn into arriving lines. Server-filtered
        rather than shipped whole because the systemwide open-order-line pool
        runs into the hundreds, the same reason that one is.

        `outstanding_only` hides lines nothing is still owed against. It is a
        default, not a rule — a vendor over-shipping an already-satisfied line
        is a real event, so the wizard exposes it as a filter the receiver can
        switch off rather than a row they can never reach.
        """
        statuses = set(OPEN_PURCHASE_ORDER_STATUSES)
        if include_draft:
            statuses.add(PurchaseOrderStatus.DRAFT)

        qs = (
            PurchaseOrderLine.objects.filter(
                deleted_at__isnull=True,
                purchase_order__domain_id__in=domain_ids,
                purchase_order__status__in=statuses,
                purchase_order__deleted_at__isnull=True,
            )
            .select_related("purchase_order", "purchase_order__vendor", "part")
        )

        if q:
            qs = qs.filter(
                Q(purchase_order__po_number__icontains=q)
                | Q(purchase_order__vendor__name__icontains=q)
                | Q(part__part_number__icontains=q)
                | Q(part__name__icontains=q)
            )
        if vendor_id is not None:
            qs = qs.filter(purchase_order__vendor_id=vendor_id)
        if purchase_order_id is not None:
            qs = qs.filter(purchase_order_id=purchase_order_id)

        qs = cls._annotate_arrival_facts(qs)
        if outstanding_only:
            qs = qs.filter(outstanding_qty__gt=0)

        return qs.order_by("purchase_order__order_date", "purchase_order_id", "line_number")

    @classmethod
    def candidates_for_arriving_part(
        cls,
        *,
        part_id: int,
        vendor_id: int | None = None,
        include_draft: bool = False,
        q: str = "",
    ) -> QuerySet[PurchaseOrderLine]:
        """Open PO lines that could account for an arriving part.

        Each candidate is annotated with what the receiver needs to make the
        call: how much was ordered, how much arrived material is already
        allocated against it, and the outstanding balance.

        `q` narrows by order number or vendor name. The part is already fixed by
        the arriving line, so there is nothing else worth searching on — this is
        the "which of this vendor's six open orders" case, not a part lookup.
        """
        statuses = set(OPEN_PURCHASE_ORDER_STATUSES)
        if include_draft:
            statuses.add(PurchaseOrderStatus.DRAFT)

        qs = cls._annotate_arrival_facts(
            PurchaseOrderLine.objects.filter(
                part_id=part_id,
                deleted_at__isnull=True,
                purchase_order__status__in=statuses,
                purchase_order__deleted_at__isnull=True,
            ).select_related("purchase_order", "purchase_order__vendor", "part")
        )

        if vendor_id is not None:
            qs = qs.filter(purchase_order__vendor_id=vendor_id)
        if q:
            qs = qs.filter(
                Q(purchase_order__po_number__icontains=q)
                | Q(purchase_order__vendor__name__icontains=q)
            )

        return qs.order_by("purchase_order__order_date", "line_number")
