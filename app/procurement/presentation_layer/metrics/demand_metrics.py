"""Metrics: PartDemand axis counts for the demand index hero.

Non-terminal ("open") sets per axis follow DemandCompletionHandler's own
terminal-state reasoning (D43) rather than re-deriving them independently —
that handler is the one place in the codebase that already had to decide,
precisely, when each axis is "done".
"""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from app.procurement.models import (
    DemandState,
    IssuanceState,
    PartDemand,
    PurchasingState,
    ShipmentState,
)

#: demand_state values where the demand itself is resolved.
_DEMAND_TERMINAL = frozenset(
    {DemandState.REJECTED, DemandState.CANCELLED, DemandState.COMPLETED}
)

#: purchasing_state values where the purchasing decision has concluded either
#: way. Unset and Approved are still open — money hasn't finished moving.
_PURCHASING_TERMINAL = frozenset(
    {PurchasingState.PURCHASED, PurchasingState.DENIED, PurchasingState.CANCELLED}
)

#: shipment_state values where the material's journey is over, one way or
#: another.
_SHIPMENT_TERMINAL = frozenset(
    {ShipmentState.DELIVERED_TO_LOCAL, ShipmentState.LOST, ShipmentState.IN_STOCK}
)

#: issuance_state values where the material has fully reached the requester.
_ISSUANCE_TERMINAL = frozenset({IssuanceState.ISSUED})


class DemandMetrics:
    @classmethod
    def summarize(cls, queryset: QuerySet[PartDemand]) -> dict:
        """One aggregate query over an already-filtered PartDemand queryset —
        never one count per tile. Caller supplies the queryset so the counts
        reflect whatever search/filter is currently applied."""
        return queryset.aggregate(
            total=Count("pk"),
            generic_open=Count("pk", filter=~Q(demand_state__in=_DEMAND_TERMINAL)),
            purchasing_open=Count(
                "pk", filter=~Q(purchasing_state__in=_PURCHASING_TERMINAL)
            ),
            shipping_open=Count("pk", filter=~Q(shipment_state__in=_SHIPMENT_TERMINAL)),
            issuance_open=Count("pk", filter=~Q(issuance_state__in=_ISSUANCE_TERMINAL)),
        )
