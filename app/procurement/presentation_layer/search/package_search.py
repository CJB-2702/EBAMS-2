"""Search: the receiving queue — filters and rollups.

Two things this module refuses to do per-row, because the legacy arrival list
did both and paid for it on every page load:

1. **Line rollups.** `line_count` / `total_shipped` / `total_accepted` are
   annotated in the list query. They all reach through the SAME join
   (``lines``), so a single join fans out once and every aggregate over it
   counts each row exactly once — this is the one shape where a plain
   ``Sum(...)`` beside a ``Count(..., distinct=True)`` is safe. Adding a second
   multi-row join here (allocations, say) would break that and would need a
   correlated subquery instead. D67.
2. **The drift flag.** ``mixed_po_assignments`` is a stored column maintained by
   PackageStatusManager, so the drift review queue is an indexed filter rather
   than a computed pass over every line.

The "no purchase order" filter is new with D71/D73's reactive receiving path.
An unattached package is not an error state — it is a box that showed up before
its paperwork — so it gets a first-class filter, not a warning.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from app.procurement.models import Package

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)


class PackageSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        status: str = "",
        vendor_id: int | None = None,
        shipment_id: str = "",
        mixed_only: bool = False,
        unattached_only: bool = False,
        arrived_from=None,
        arrived_to=None,
        q: str = "",
    ) -> QuerySet[Package]:
        """The package list, domain-scoped (D5) and annotated once.

        ``domain_ids`` is not optional. An empty list means the user has no
        domain access and therefore sees nothing — the intended reading, not a
        bug to paper over by skipping the filter.
        """
        qs = (
            Package.objects.filter(domain_id__in=domain_ids, deleted_at__isnull=True)
            .select_related("purchase_order", "purchase_order__vendor", "domain")
            .annotate(
                line_count=Count(
                    "lines", filter=Q(lines__deleted_at__isnull=True), distinct=True
                ),
                total_shipped=Coalesce(
                    Sum("lines__quantity", filter=Q(lines__deleted_at__isnull=True)),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
                total_accepted=Coalesce(
                    Sum(
                        "lines__quantity_accepted",
                        filter=Q(lines__deleted_at__isnull=True),
                    ),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
            )
        )

        if status:
            qs = qs.filter(status=status)
        if vendor_id is not None:
            qs = qs.filter(purchase_order__vendor_id=vendor_id)
        if shipment_id:
            # Receivers search by what is printed on the box, so this is a
            # contains match on the string as typed, not an exact lookup.
            qs = qs.filter(shipment_id__icontains=shipment_id)
        if mixed_only:
            qs = qs.filter(mixed_po_assignments=True)
        if unattached_only:
            qs = qs.filter(purchase_order__isnull=True)
        if arrived_from:
            qs = qs.filter(expected_arrival_date__gte=arrived_from)
        if arrived_to:
            qs = qs.filter(expected_arrival_date__lte=arrived_to)
        if q:
            qs = qs.filter(
                Q(package_number__icontains=q)
                | Q(shipment_id__icontains=q)
                | Q(carrier__icontains=q)
                | Q(notes__icontains=q)
                | Q(purchase_order__po_number__icontains=q)
            )

        return qs.order_by("-created_at")
