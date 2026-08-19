"""Context: entry point for control logic around one Action id.

Domain verbs for the ActionStatus lifecycle. Completion side effects that
would touch PartDemand state are deliberately NOT here — Maintenance never
writes procurement.PartDemand state directly (D7); a caller that wants a
part demand cancelled/reissued alongside an action outcome does that
explicitly through app.procurement's own PartDemandContext.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.maintenance.control_layer.domain_structs.action_struct import ActionStruct
from app.maintenance.models.action import Action, ActionStatus

TERMINAL_STATUSES = frozenset(
    {ActionStatus.COMPLETE, ActionStatus.FAILED, ActionStatus.SKIPPED}
)


class ActionContext:
    def __init__(self, action_id: int) -> None:
        self.action_id = action_id
        self._struct: ActionStruct | None = None

    @classmethod
    def from_struct(cls, struct: ActionStruct) -> "ActionContext":
        context = cls(struct.action_id)
        context._struct = struct
        return context

    @property
    def struct(self) -> ActionStruct:
        if self._struct is None:
            self._struct = ActionStruct.load(action_id=self.action_id)
        return self._struct

    @property
    def action(self) -> Action:
        return self.struct.action

    def refresh(self) -> None:
        self._struct = None

    def _handle_user_assignment(self, action: Action, *, actor, new_status: str) -> None:
        if action.assigned_user_id is None and actor is not None:
            action.assigned_user = actor
            if action.assigned_by_id is None:
                action.assigned_by = actor
        if new_status in TERMINAL_STATUSES:
            completed_by = actor or action.assigned_user
            if completed_by is not None:
                action.completed_by = completed_by

    def start(self, *, actor=None) -> Action:
        action = self.action
        if action.status != ActionStatus.NOT_STARTED:
            return action
        action.status = ActionStatus.IN_PROGRESS
        action.start_time = timezone.now()
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.IN_PROGRESS)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def complete(
        self, *, actor=None, billable_hours: float | None = None, notes: str = ""
    ) -> Action:
        action = self.action
        if action.status not in (
            ActionStatus.NOT_STARTED,
            ActionStatus.IN_PROGRESS,
            ActionStatus.BLOCKED,
        ):
            return action
        action.status = ActionStatus.COMPLETE
        action.end_time = timezone.now()
        if billable_hours is not None:
            action.billable_hours = billable_hours
        if notes:
            action.completion_notes = notes
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.COMPLETE)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def mark_failed(
        self, *, actor=None, billable_hours: float | None = None, notes: str = ""
    ) -> Action:
        action = self.action
        if action.status not in (
            ActionStatus.NOT_STARTED,
            ActionStatus.IN_PROGRESS,
            ActionStatus.BLOCKED,
        ):
            return action
        action.status = ActionStatus.FAILED
        action.end_time = timezone.now()
        if billable_hours is not None:
            action.billable_hours = billable_hours
        if notes:
            action.completion_notes = notes
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.FAILED)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def mark_skipped(self, *, actor=None, notes: str = "") -> Action:
        action = self.action
        if action.status not in (
            ActionStatus.NOT_STARTED,
            ActionStatus.IN_PROGRESS,
            ActionStatus.BLOCKED,
        ):
            return action
        action.status = ActionStatus.SKIPPED
        if notes:
            action.completion_notes = notes
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.SKIPPED)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def mark_blocked(self, *, actor=None, notes: str = "") -> Action:
        """Work on THIS STEP has stopped. The job as a whole has not.

        There are two different blocking concepts in this app and they must
        not be merged:

        * ``Action.status = Blocked`` (here) — one step cannot proceed. The
          technician moves on to the next step. Nothing else changes: no
          MaintenanceBlocker row is created and MaintenanceDetail.status is
          NOT touched. Deliberately writes only this Action.
        * ``MaintenanceBlocker`` (MaintenanceBlockerManager.add_blocker) —
          the whole maintenance activity is stopped. That one hangs off the
          maintenance header, flips the event to Blocked, can re-prioritise
          the event, records billable hours lost, and holds completion open.

        A step being blocked is an ordinary working condition; an event being
        blocked is an escalation someone has to answer for. If this method
        ever starts creating MaintenanceBlocker rows, that distinction is
        gone and every "step waiting on a torque wrench" becomes a reportable
        work stoppage.

        Deliberately NOT terminal (see TERMINAL_STATUSES): a blocked step is
        expected to come back via reopen(), so end_time stays unset and no
        completed_by is stamped — nobody finished anything.
        """
        action = self.action
        if action.status not in (ActionStatus.NOT_STARTED, ActionStatus.IN_PROGRESS):
            return action
        action.status = ActionStatus.BLOCKED
        if notes:
            action.completion_notes = notes
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.BLOCKED)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def reopen(self, *, actor=None, notes: str = "") -> Action:
        """Put a settled step back to In Progress — the legacy "Resume" (from
        Blocked) and "Change" (from Complete/Failed) verbs, which are the same
        transition with different button labels.

        Clears end_time because the step is no longer finished, and backfills
        start_time when reopening something that was skipped without ever
        having been started.
        """
        action = self.action
        if action.status not in (
            ActionStatus.BLOCKED,
            ActionStatus.COMPLETE,
            ActionStatus.FAILED,
            ActionStatus.SKIPPED,
        ):
            return action
        action.status = ActionStatus.IN_PROGRESS
        action.end_time = None
        action.start_time = action.start_time or timezone.now()
        if notes:
            action.completion_notes = notes
        self._handle_user_assignment(action, actor=actor, new_status=ActionStatus.IN_PROGRESS)
        action.updated_by = actor
        action.save()
        self.refresh()
        return action

    def assign(self, *, assigned_user, assigned_by=None, actor=None) -> Action:
        action = self.action
        action.assigned_user = assigned_user
        action.assigned_by = assigned_by or assigned_user
        action.updated_by = actor or assigned_by or assigned_user
        action.save(update_fields=["assigned_user", "assigned_by", "updated_by", "updated_at"])
        self.refresh()
        return action

    def reorder(self, *, new_sequence_order: int, actor=None) -> Action:
        """Move this action to a new position within its event, shifting the
        others to keep sequence_order dense and unique."""
        if new_sequence_order < 1:
            raise ValueError("Sequence order must be at least 1.")

        action = self.action
        current_order = action.sequence_order
        siblings = list(
            Action.objects.filter(
                event_detail_id=action.event_detail_id, deleted_at__isnull=True
            ).exclude(pk=action.pk)
        )
        max_order = len(siblings) + 1
        if new_sequence_order > max_order:
            raise ValueError(f"Sequence order cannot exceed {max_order}.")
        if current_order == new_sequence_order:
            return action

        with transaction.atomic():
            if new_sequence_order < current_order:
                for sibling in siblings:
                    if new_sequence_order <= sibling.sequence_order < current_order:
                        sibling.sequence_order += 1
                        sibling.save(update_fields=["sequence_order"])
            else:
                for sibling in siblings:
                    if current_order < sibling.sequence_order <= new_sequence_order:
                        sibling.sequence_order -= 1
                        sibling.save(update_fields=["sequence_order"])
            action.sequence_order = new_sequence_order
            action.updated_by = actor
            action.save(update_fields=["sequence_order", "updated_by", "updated_at"])
        self.refresh()
        return action

    def edit(self, *, actor=None, **fields) -> Action:
        """Patch plain fields (and, optionally, status with no side effects beyond
        the raw assignment — use start()/complete()/mark_failed()/mark_skipped()
        when the transition should carry its usual side effects)."""
        action = self.action
        update_fields: list[str] = []
        editable = (
            "action_name",
            "description",
            "instructions",
            "estimated_duration_minutes",
            "safety_notes",
            "notes",
            "scheduled_start_time",
            "start_time",
            "end_time",
            "billable_hours",
            "completion_notes",
            "status",
        )
        for field_name in editable:
            if field_name in fields and fields[field_name] is not None:
                setattr(action, field_name, fields[field_name])
                update_fields.append(field_name)
        if update_fields:
            action.updated_by = actor
            update_fields += ["updated_by", "updated_at"]
            action.save(update_fields=update_fields)
        self.refresh()
        return action
