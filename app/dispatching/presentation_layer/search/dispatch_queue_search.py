"""Read helpers for the dispatcher queue and requester dashboard. Drops the
outcome-type and location filter dimensions legacy had — neither concept
exists any more (design_drift.md §2.2, §2.9)."""

from __future__ import annotations

from django.db.models import QuerySet

from app.events.models.details.dispatching import DispatchingDetail

_QUEUE_STATUSES = ("submitted", "under_review", "fixes_requested")


def search_dispatcher_queue(*, domain_ids=None, workflow_status: str = "") -> QuerySet[DispatchingDetail]:
    qs = DispatchingDetail.objects.filter(deleted_at__isnull=True).select_related(
        "requested_for", "requested_by", "asset_class", "domain"
    )
    if domain_ids is not None:
        qs = qs.filter(domain_id__in=domain_ids)
    if workflow_status:
        qs = qs.filter(workflow_status=workflow_status)
    else:
        qs = qs.filter(workflow_status__in=_QUEUE_STATUSES)
    return qs.order_by("-priority", "desired_start")


def search_my_dispatches(*, requested_for_id: int) -> QuerySet[DispatchingDetail]:
    return (
        DispatchingDetail.objects.filter(deleted_at__isnull=True, requested_for_id=requested_for_id)
        .select_related("asset_class", "domain")
        .order_by("-created_at")
    )
