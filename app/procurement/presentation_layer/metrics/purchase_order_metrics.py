"""Metrics: PurchaseOrder status counts for the purchase-order index hero."""

from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from app.procurement.models import PurchaseOrder, PurchaseOrderStatus


class PurchaseOrderMetrics:
    @classmethod
    def summarize(cls, queryset: QuerySet[PurchaseOrder]) -> dict:
        """One aggregate query over an already-filtered PurchaseOrder
        queryset. Cancelled is excluded — the four tiles are the working
        lifecycle, not the whole status enum."""
        return queryset.aggregate(
            draft=Count("pk", filter=Q(status=PurchaseOrderStatus.DRAFT)),
            placed=Count("pk", filter=Q(status=PurchaseOrderStatus.PLACED)),
            partially_received=Count(
                "pk", filter=Q(status=PurchaseOrderStatus.PARTIALLY_RECEIVED)
            ),
            received=Count("pk", filter=Q(status=PurchaseOrderStatus.RECEIVED)),
        )
