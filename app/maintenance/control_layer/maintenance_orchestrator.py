"""Orchestrator: coordinates an Action status change with its parent
MaintenanceDetail — auto-starting the event, auto-assigning the first
technician who touches it, and keeping actual_billable_hours in sync.

Exists because these three side effects span two aggregates (Action +
MaintenanceDetail) that ActionContext alone has no business reaching across.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.events.models.event import EventStatus
from app.maintenance.control_layer.action_context import ActionContext
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.models.action import ActionStatus


class MaintenanceOrchestrator:
    def __init__(self, maintenance_detail_id: int) -> None:
        self._ctx = MaintenanceContext(maintenance_detail_id)

    def update_action_status(
        self,
        *,
        action_id: int,
        new_status: str,
        actor=None,
        billable_hours: float | None = None,
        notes: str = "",
    ):
        action_ctx = ActionContext(action_id)
        with transaction.atomic():
            if new_status == ActionStatus.IN_PROGRESS:
                action = action_ctx.start(actor=actor)
            elif new_status == ActionStatus.COMPLETE:
                action = action_ctx.complete(
                    actor=actor, billable_hours=billable_hours, notes=notes
                )
            elif new_status == ActionStatus.FAILED:
                action = action_ctx.mark_failed(
                    actor=actor, billable_hours=billable_hours, notes=notes
                )
            elif new_status == ActionStatus.SKIPPED:
                action = action_ctx.mark_skipped(actor=actor, notes=notes)
            else:
                action = action_ctx.edit(status=new_status, actor=actor)

            # Skipping an action is not "starting work" — don't auto-assign for it.
            if new_status != ActionStatus.SKIPPED:
                self._ctx.assignment_manager.auto_assign(actor=actor)

            detail = self._ctx.maintenance_detail
            if detail.status == EventStatus.PLANNED:
                detail.status = EventStatus.IN_PROGRESS
                detail.event_start = detail.event_start or timezone.now()
                detail.updated_by = actor
                detail.save(
                    update_fields=["status", "event_start", "updated_by", "updated_at"]
                )
                self._ctx.refresh()

            self._ctx.billable_hours_manager.auto_update_if_greater(actor=actor)
        return action
