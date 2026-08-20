"""Read helpers for the template picker and management list. Head revisions
only — superseded and retired revisions are readable from a lineage's own
history page, never offered here (dispatching_starter_kit/
1_dispatch_templates.md §7)."""

from __future__ import annotations

from django.db.models import QuerySet

from app.dispatching.models.templates.dispatch_template import DispatchTemplate


def search_templates_for_picker(*, domain_ids=None, q: str = "") -> QuerySet[DispatchTemplate]:
    """Head revisions only, not retired — what a requester may raise a
    dispatch from."""
    qs = DispatchTemplate.objects.filter(
        is_retired=False, head_revision__isnull=False
    ).select_related("head_revision", "domain")
    if domain_ids is not None:
        qs = qs.filter(domain_id__in=domain_ids)
    q = (q or "").strip()
    if q:
        qs = qs.filter(head_revision__title__icontains=q)
    return qs.order_by("head_revision__title")


def search_templates_for_management(*, domain_ids=None, include_retired: bool = True) -> QuerySet[DispatchTemplate]:
    qs = DispatchTemplate.objects.select_related("head_revision", "domain")
    if domain_ids is not None:
        qs = qs.filter(domain_id__in=domain_ids)
    if not include_retired:
        qs = qs.filter(is_retired=False)
    return qs.order_by("head_revision__title")
