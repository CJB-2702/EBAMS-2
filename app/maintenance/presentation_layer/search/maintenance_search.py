"""Search: domain-scoped QuerySet filters for the Maintenance event ledger.

Legacy: presentation/routes/maintenance/search_utils.py. Maintenance events
are events.MaintenanceDetail rows (MTI over events.Event) — every query here
starts from MaintenanceDetail.objects (not Event.objects), so callers get the
maintenance-specific fields (asset, maintenance_type, work_order_reference)
without a second join.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.events.models.details.maintenance import MaintenanceDetail


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
    ) -> QuerySet[MaintenanceDetail]:
        """The maintenance_index page — one canonical list (D5-scoped). A
        Technician's "my work" view is this with `assigned_user_id=request.user.pk`,
        the Planner's queue is this with a sparse `status` filter."""
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
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(work_order_reference__icontains=q)
                | Q(asset__name__icontains=q)
                | Q(asset__serial_number__icontains=q)
            )

        return qs.order_by("-event_start")
