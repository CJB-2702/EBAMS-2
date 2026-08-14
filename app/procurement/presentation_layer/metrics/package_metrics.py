"""Metrics: Package status counts for the package index hero."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from app.procurement.models import Package, PackageStatus

#: Still moving through the vendor/carrier pipeline — everything short of
#: arriving locally, being accepted, or falling out of the flow entirely.
_IN_PROGRESS_STATUSES = frozenset(
    {
        PackageStatus.AWAITING_SHIPMENT,
        PackageStatus.BACKORDERED,
        PackageStatus.SHIPPED,
        PackageStatus.DELIVERED_TO_DEPOT,
    }
)

_LOST_OR_CANCELLED_STATUSES = frozenset({PackageStatus.LOST, PackageStatus.CANCELLED})


class PackageMetrics:
    @classmethod
    def summarize(cls, queryset: QuerySet[Package]) -> dict:
        """One aggregate query over an already-filtered Package queryset."""
        return queryset.aggregate(
            delivered_to_local=Count(
                "pk", filter=Q(status=PackageStatus.DELIVERED_TO_LOCAL)
            ),
            accepted=Count("pk", filter=Q(status=PackageStatus.ACCEPTED)),
            lost_or_cancelled=Count(
                "pk", filter=Q(status__in=_LOST_OR_CANCELLED_STATUSES)
            ),
            in_progress=Count("pk", filter=Q(status__in=_IN_PROGRESS_STATUSES)),
        )
