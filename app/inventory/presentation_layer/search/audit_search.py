"""Search: the audit dashboard (`/inventory/audits`) and the audit log
ledger (`/inventory/audit-logs`)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.inventory.models.audit.audit_session import AuditSession
from app.inventory.models.audit.inventory_audit_log import InventoryAuditLog
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)


class AuditSearch:
    @classmethod
    def session_list(
        cls,
        *,
        domain_ids,
        status: str = "",
        session_type: str = "",
        warehouse_id: str = "",
    ) -> QuerySet[AuditSession]:
        visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
        qs = AuditSession.objects.filter(
            Q(room_id__in=visible_room_ids) | Q(room__isnull=True)
        ).select_related("warehouse", "room", "conducted_by")

        if status:
            qs = qs.filter(status=status)
        if session_type:
            qs = qs.filter(session_type=session_type)
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        return qs.order_by("-started_at")

    @classmethod
    def log_list(
        cls,
        *,
        domain_ids,
        reason_code: str = "",
        part_q: str = "",
        warehouse_id: str = "",
    ) -> QuerySet[InventoryAuditLog]:
        visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
        qs = InventoryAuditLog.objects.filter(
            room_id__in=visible_room_ids
        ).select_related("part", "warehouse", "room", "recorded_by", "line", "line__session")

        if reason_code:
            qs = qs.filter(reason_code=reason_code)
        if part_q:
            qs = qs.filter(
                Q(part__part_number__icontains=part_q) | Q(part__name__icontains=part_q)
            )
        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        return qs.order_by("-recorded_at")
