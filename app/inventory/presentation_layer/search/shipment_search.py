"""Search: the Inventory-side read of procurement's `Shipment` table (D84).

Plain queryset reads only — no import of `app.procurement.presentation_layer`
or `app.procurement.control_layer.domain_structs`. D84 explicitly scopes
Inventory's reads to "plain queryset reads are the appropriate boundary
here", the same boundary every other read-only cross-app data access in this
codebase uses (see `app.inventory.control_layer.orchestrators.
part_issuance_orchestrator` importing `procurement.models` directly). This
keeps Inventory decoupled from procurement's own presentation-layer
internals, which are free to reshape without breaking this module.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from app.procurement.models import Shipment

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)


class InventoryShipmentSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        status: str = "",
        shipment_id: str = "",
        q: str = "",
    ) -> QuerySet[Shipment]:
        """The inventory receiving view of the shipment list, domain-scoped
        (D5) the same way procurement's own `ShipmentSearch.index_list` is.
        """
        qs = (
            Shipment.objects.filter(domain_id__in=domain_ids, deleted_at__isnull=True)
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
        if shipment_id:
            qs = qs.filter(shipment_id__icontains=shipment_id)
        if q:
            qs = qs.filter(
                Q(shipment_number__icontains=q)
                | Q(shipment_id__icontains=q)
                | Q(carrier__icontains=q)
                | Q(notes__icontains=q)
                | Q(purchase_order__po_number__icontains=q)
            )

        return qs.order_by("-created_at")
