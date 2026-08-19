"""Context: entry point for control logic around one MaintenanceDetail id.

Owns status changes and the R4 completion workflow directly; delegates
sub-domain behavior (blockers, asset limitations, billable hours, assignment,
action creation) to stable Manager collaborators exposed as properties.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventStatus
from app.maintenance.control_layer.domain_structs.maintenance_detail_struct import (
    MaintenanceDetailStruct,
)
from app.maintenance.control_layer.guards.maintenance_completion_guard import (
    CompletionVerdict,
    MaintenanceCompletionPolicy,
)

#: Statuses complete()/cancel() may transition out of. Blocked/Cancelled/Complete/
#: Failed/Skipped are terminal or guard-owned and never targeted directly here.
_OPEN_STATUSES = (EventStatus.PLANNED, EventStatus.IN_PROGRESS, EventStatus.BLOCKED)


class MaintenanceContext:
    def __init__(self, maintenance_detail_id: int) -> None:
        self.maintenance_detail_id = maintenance_detail_id
        self._struct: MaintenanceDetailStruct | None = None

    @classmethod
    def from_struct(cls, struct: MaintenanceDetailStruct) -> "MaintenanceContext":
        """Build from a pre-loaded struct. Issues no DB queries."""
        context = cls(struct.maintenance_detail_id)
        context._struct = struct
        return context

    @property
    def struct(self) -> MaintenanceDetailStruct:
        if self._struct is None:
            self._struct = MaintenanceDetailStruct.load(
                maintenance_detail_id=self.maintenance_detail_id
            )
        return self._struct

    @property
    def maintenance_detail(self) -> MaintenanceDetail:
        return self.struct.maintenance_detail

    def refresh(self) -> None:
        self._struct = None

    # ------------------------------------------------------------------ #
    # Sub-managers — stable collaborators, one per sub-domain
    # ------------------------------------------------------------------ #

    @property
    def blocker_manager(self):
        from app.maintenance.control_layer.maintenance_blocker_manager import (
            MaintenanceBlockerManager,
        )

        return MaintenanceBlockerManager(self)

    @property
    def limitation_manager(self):
        from app.maintenance.control_layer.asset_limitation_manager import (
            AssetLimitationManager,
        )

        return AssetLimitationManager(self)

    @property
    def billable_hours_manager(self):
        from app.maintenance.control_layer.billable_hours_manager import (
            BillableHoursManager,
        )

        return BillableHoursManager(self)

    @property
    def assignment_manager(self):
        from app.maintenance.control_layer.maintenance_assignment_manager import (
            MaintenanceAssignmentManager,
        )

        return MaintenanceAssignmentManager(self)

    @property
    def action_creation_manager(self):
        from app.maintenance.control_layer.action_creation_manager import (
            ActionCreationManager,
        )

        return ActionCreationManager(self)

    # ------------------------------------------------------------------ #
    # Domain verbs
    # ------------------------------------------------------------------ #

    def start(self, *, actor=None) -> MaintenanceDetail:
        detail = self.maintenance_detail
        if detail.status not in (EventStatus.PLANNED, None):
            return detail
        detail.status = EventStatus.IN_PROGRESS
        detail.event_start = detail.event_start or timezone.now()
        detail.updated_by = actor
        detail.save(update_fields=["status", "event_start", "updated_by", "updated_at"])
        self.refresh()
        return detail

    def completion_verdict(self) -> CompletionVerdict:
        """R4, read-only: what (if anything) is blocking completion right now —
        exposed so the UI can show the technician what's left before they try."""
        return MaintenanceCompletionPolicy.check(struct=self.struct)

    def complete(self, *, actor=None, notes: str = "") -> MaintenanceDetail:
        """R4: every Action must be Complete/Skipped, every blocker resolved, every
        asset limitation record closed. Refuses with the unmet reasons rather than
        silently no-opping."""
        verdict = self.completion_verdict()
        if not verdict.allowed:
            raise ValueError("; ".join(verdict.reasons))

        detail = self.maintenance_detail
        with transaction.atomic():
            detail.status = EventStatus.COMPLETE
            detail.event_end = timezone.now()
            if actor is not None:
                detail.completed_by = actor
                # Auto-assign if nobody claimed it — mirrors the legacy rule that
                # whoever closes out the work is the assignee of record.
                if detail.assigned_user_id is None:
                    detail.assigned_user = actor
                    detail.assigned_by = actor
            if notes:
                detail.completion_notes = notes
            detail.updated_by = actor
            detail.save()
        self.refresh()
        return detail

    def cancel(self, *, actor=None, notes: str = "") -> MaintenanceDetail:
        detail = self.maintenance_detail
        if detail.status not in (EventStatus.PLANNED, EventStatus.IN_PROGRESS):
            return detail
        detail.status = EventStatus.CANCELLED
        detail.event_end = timezone.now()
        if notes:
            detail.completion_notes = notes
        detail.updated_by = actor
        detail.save()
        self.refresh()
        return detail

    def add_comment(self, post_data, *, actor, is_human_made: bool = True):
        """MaintenanceDetail IS an Event row (MTI) sharing the same pk — comments
        are event comments, so this is a thin pass-through to EventContext rather
        than a duplicate comment path.

        `is_human_made=False` marks a machine-written narration (a blocker
        opening, a limitation closing) so the activity log's Human/Machine
        filter can separate what a person said from what the system recorded.
        """
        from app.events.control_layer.event_context import EventContext

        return EventContext(self.maintenance_detail_id, actor).add_comment(
            post_data, is_human_made=is_human_made
        )
