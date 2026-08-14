"""Metrics: Shipment status counts for the shipment index hero."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from app.procurement.models import Shipment, ShipmentStatus

#: Still moving through the vendor/carrier pipeline — everything short of
#: arriving locally, being accepted, or falling out of the flow entirely.
_IN_PROGRESS_STATUSES = frozenset(
    {
        ShipmentStatus.AWAITING_SHIPMENT,
        ShipmentStatus.BACKORDERED,
        ShipmentStatus.SHIPPED,
        ShipmentStatus.DELIVERED_TO_DEPOT,
    }
)

_LOST_OR_CANCELLED_STATUSES = frozenset({ShipmentStatus.LOST, ShipmentStatus.CANCELLED})


class ShipmentMetrics:
    @classmethod
    def summarize(cls, queryset: QuerySet[Shipment]) -> dict:
        """One aggregate query over an already-filtered Shipment queryset."""
        return queryset.aggregate(
            delivered_to_local=Count(
                "pk", filter=Q(status=ShipmentStatus.DELIVERED_TO_LOCAL)
            ),
            accepted=Count("pk", filter=Q(status=ShipmentStatus.ACCEPTED)),
            lost_or_cancelled=Count(
                "pk", filter=Q(status__in=_LOST_OR_CANCELLED_STATUSES)
            ),
            in_progress=Count("pk", filter=Q(status__in=_IN_PROGRESS_STATUSES)),
        )
