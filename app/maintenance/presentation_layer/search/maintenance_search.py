"""Search: domain-scoped QuerySet filters for the Maintenance event ledger.

Legacy: presentation/routes/maintenance/search_utils.py. Maintenance events
are events.MaintenanceDetail rows (MTI over events.Event) — every query here
starts from MaintenanceDetail.objects (not Event.objects), so callers get the
maintenance-specific fields (asset, maintenance_type, work_order_reference)
without a second join.
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet

from app.events.models.details.maintenance import MaintenanceDetail
from app.maintenance.models.asset_limitation import AssetLimitationRecord
from app.maintenance.models.blocker import MaintenanceBlocker


def _active_blocker_exists() -> Exists:
    """``.filter(blockers__end_date__isnull=True)`` would also match events
    with NO blockers at all — the reverse-relation LEFT JOIN makes a missing
    row's ``end_date`` read as NULL too, which satisfies ``isnull=True`` just
    as an actually-open blocker would. ``Exists`` tests for a matching row
    instead of a nullable column reached through an outer join."""
    return Exists(
        MaintenanceBlocker.objects.filter(
            maintenance_detail_id=OuterRef("pk"),
            end_date__isnull=True,
            deleted_at__isnull=True,
        )
    )


def _active_limitation_exists() -> Exists:
    return Exists(
        AssetLimitationRecord.objects.filter(
            maintenance_detail_id=OuterRef("pk"),
            end_time__isnull=True,
            deleted_at__isnull=True,
        )
    )


class MaintenanceSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        status: str = "",
        asset_id: int | None = None,
        priority: str = "",
        maintenance_type: str = "",
        work_order_reference: str = "",
        assigned_user_id: int | None = None,
        q: str = "",
        domain_id: int | None = None,
        asset_class: str = "",
        model: str = "",
        manufacturer: str = "",
        date_from=None,
        date_to=None,
        has_blockers: bool = False,
        has_limitations: bool = False,
        action_title: str = "",
        created_by_id: int | None = None,
        commented_by_id: int | None = None,
    ) -> QuerySet[MaintenanceDetail]:
        """The maintenance_index page — one canonical list (D5-scoped). A
        Technician's "my work" view is this with `assigned_user_id=request.user.pk`,
        the Planner's queue is this with a sparse `status` filter.

        `manufacturer` (a real M2M join) and `action_title`/`commented_by_id`
        (one-to-many joins) can multiply rows for an event with several
        matching children, so this calls `.distinct()` whenever one of those
        is active. `has_blockers`/`has_limitations` use `Exists()` subqueries
        instead and never multiply rows."""
        qs = (
            MaintenanceDetail.objects.filter(
                domain_id__in=domain_ids, deleted_at__isnull=True
            )
            .select_related("domain", "asset", "assigned_user", "template_action_set")
        )

        if status:
            qs = qs.filter(status=status)
        if asset_id:
            qs = qs.filter(asset_id=asset_id)
        if priority:
            qs = qs.filter(priority=priority)
        if maintenance_type:
            qs = qs.filter(maintenance_type=maintenance_type)
        if work_order_reference:
            qs = qs.filter(work_order_reference__icontains=work_order_reference)
        if assigned_user_id:
            qs = qs.filter(assigned_user_id=assigned_user_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if created_by_id:
            qs = qs.filter(created_by_id=created_by_id)
        if date_from:
            qs = qs.filter(event_start__gte=date_from)
        if date_to:
            qs = qs.filter(event_start__lte=date_to)
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(work_order_reference__icontains=q)
                | Q(asset__name__icontains=q)
                | Q(asset__serial_number__icontains=q)
            )

        needs_distinct = False
        if asset_class:
            qs = qs.filter(asset__asset_class_id=asset_class)
        if model:
            qs = qs.filter(asset__model_id=model)
        if manufacturer:
            qs = qs.filter(asset__model__manufacturers__id=manufacturer)
            needs_distinct = True
        if has_blockers:
            qs = qs.filter(_active_blocker_exists())
        if has_limitations:
            qs = qs.filter(_active_limitation_exists())
        if action_title:
            qs = qs.filter(
                actions__action_name__icontains=action_title,
                actions__deleted_at__isnull=True,
            )
            needs_distinct = True
        if commented_by_id:
            qs = qs.filter(comments__created_by_id=commented_by_id)
            needs_distinct = True

        if needs_distinct:
            qs = qs.distinct()

        return qs.order_by("-event_start")

    @classmethod
    def recently_interacted(
        cls, *, domain_ids, user_id: int, limit: int = 5
    ) -> list[MaintenanceDetail]:
        """Maintenance events the given user has commented on, most-recently
        commented first. Legacy: technician/continue-discussion, which jumped
        straight to the single latest thread — this renders the same ranking
        as a list instead of a redirect (page_catalog.md #17)."""
        from app.events.models.comment import Comment

        thread_ids: list[int] = []
        seen: set[int] = set()
        # Comments span every event type; over-scan a bit so enough of them
        # turn out to be maintenance events to fill `limit`.
        for thread_id in (
            Comment.objects.visible()
            .filter(created_by_id=user_id)
            .order_by("-created_at")
            .values_list("activity_thread_id", flat=True)[: limit * 20]
        ):
            if thread_id not in seen:
                seen.add(thread_id)
                thread_ids.append(thread_id)

        if not thread_ids:
            return []

        by_id = {
            event.pk: event
            for event in MaintenanceDetail.objects.filter(
                pk__in=thread_ids, domain_id__in=domain_ids, deleted_at__isnull=True
            ).select_related("asset")
        }
        return [by_id[tid] for tid in thread_ids if tid in by_id][:limit]
