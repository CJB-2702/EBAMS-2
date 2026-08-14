"""Search: the splitting wizard's PO lookup.

THIS IS THE WIZARD'S REAL WORK. Finding the right line across a vendor's open
orders is the hard part, not the arithmetic — which is why line splitting gets
a wizard at all.
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

from app.procurement.models import ShipmentLine, PurchaseOrderLine, PurchaseOrderStatus

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
    def candidates_for_arriving_part(
        cls,
        *,
        part_id: int,
        vendor_id: int | None = None,
        include_draft: bool = False,
    ) -> QuerySet[PurchaseOrderLine]:
        """Open PO lines that could account for an arriving part.

        Each candidate is annotated with what the wizard needs to make the
        call: how much was ordered, how much has already been accepted against
        it, and the outstanding balance.
        """
        statuses = set(OPEN_PURCHASE_ORDER_STATUSES)
        if include_draft:
            statuses.add(PurchaseOrderStatus.DRAFT)

        qs = (
            PurchaseOrderLine.objects.filter(
                part_id=part_id,
                deleted_at__isnull=True,
                purchase_order__status__in=statuses,
                purchase_order__deleted_at__isnull=True,
            )
            .select_related("purchase_order", "purchase_order__vendor", "part")
            .annotate(
                # A correlated subquery, not a joined Sum: annotating a Sum
                # over shipment_lines alongside the allocations Count below
                # would fan out and multiply the accepted quantity by the
                # number of allocations.
                qty_from_accepted_shipments=Coalesce(
                    Subquery(
                        ShipmentLine.objects.filter(
                            purchase_order_line=OuterRef("pk"),
                            deleted_at__isnull=True,
                        )
                        .values("purchase_order_line")
                        .annotate(total=Sum("quantity_accepted"))
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
            )
            .annotate(
                # quantity_ordered is a per-row field — subtract directly
                # rather than aggregating it across a join.
                outstanding_qty=F("quantity_ordered")
                - F("qty_from_accepted_shipments"),
            )
        )

        if vendor_id is not None:
            qs = qs.filter(purchase_order__vendor_id=vendor_id)

        return qs.order_by("purchase_order__order_date", "line_number")
