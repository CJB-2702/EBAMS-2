"""Manager: blockers sub-domain for one MaintenanceDetail
(MaintenanceContext.blocker_manager).

Owns MaintenanceBlocker creation/resolution and keeps MaintenanceDetail.status
in sync — opening a blocker moves the event to Blocked; resolving the last
active blocker returns it to In Progress.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.events.models.event import EventStatus
from app.maintenance.models.blocker import BlockerPriority, MaintenanceBlocker


class MaintenanceBlockerManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    @property
    def active_blockers(self) -> list[MaintenanceBlocker]:
        return self._ctx.struct.active_blockers

    def add_blocker(
        self,
        *,
        reason: str,
        notes: str = "",
        start_date=None,
        billable_hours: float | None = None,
        priority: str = BlockerPriority.MEDIUM,
        expected_resolution_date=None,
        actor=None,
    ) -> MaintenanceBlocker:
        """Only one active blocker per event at a time — a second cannot be opened
        while the first is unresolved."""
        if self.active_blockers:
            raise ValueError(
                "An active blocker already exists. Resolve it before adding another."
            )

        detail = self._ctx.maintenance_detail
        with transaction.atomic():
            blocker = MaintenanceBlocker.objects.create(
                maintenance_detail=detail,
                reason=reason,
                notes=notes,
                start_date=start_date or timezone.now(),
                billable_hours=billable_hours,
                priority=priority,
                expected_resolution_date=expected_resolution_date,
                created_by=actor,
                updated_by=actor,
            )
            if detail.status in (EventStatus.PLANNED, EventStatus.IN_PROGRESS):
                detail.status = EventStatus.BLOCKED
                if notes:
                    detail.blocker_notes = notes
                detail.updated_by = actor
                detail.save(
                    update_fields=["status", "blocker_notes", "updated_by", "updated_at"]
                )
        self._ctx.refresh()
        return blocker

    def end_blocker(self, *, blocker_id: int, end_date=None, actor=None) -> MaintenanceBlocker:
        blocker = MaintenanceBlocker.objects.get(
            pk=blocker_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        if blocker.end_date is not None:
            return blocker

        detail = self._ctx.maintenance_detail
        with transaction.atomic():
            blocker.end_date = end_date or timezone.now()
            blocker.updated_by = actor
            blocker.save(update_fields=["end_date", "updated_by", "updated_at"])

            remaining = (
                MaintenanceBlocker.objects.filter(
                    maintenance_detail_id=self._ctx.maintenance_detail_id,
                    end_date__isnull=True,
                    deleted_at__isnull=True,
                )
                .exclude(pk=blocker_id)
                .exists()
            )
            if not remaining and detail.status == EventStatus.BLOCKED:
                detail.status = EventStatus.IN_PROGRESS
                detail.updated_by = actor
                detail.save(update_fields=["status", "updated_by", "updated_at"])
        self._ctx.refresh()
        return blocker

    def update_blocker(self, *, blocker_id: int, actor=None, **fields) -> MaintenanceBlocker:
        blocker = MaintenanceBlocker.objects.get(
            pk=blocker_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        update_fields: list[str] = []
        for field_name in (
            "reason",
            "notes",
            "start_date",
            "billable_hours",
            "priority",
            "expected_resolution_date",
        ):
            if field_name in fields and fields[field_name] is not None:
                setattr(blocker, field_name, fields[field_name])
                update_fields.append(field_name)
        if update_fields:
            blocker.updated_by = actor
            update_fields += ["updated_by", "updated_at"]
            blocker.save(update_fields=update_fields)
        self._ctx.refresh()
        return blocker
