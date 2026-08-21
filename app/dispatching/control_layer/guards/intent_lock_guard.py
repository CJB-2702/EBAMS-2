"""Guard type: Policy. Once a dispatch reaches Planned, AlternateResolution,
or Rejected, its intent freezes — desired dates, asset class/subclass,
scope, who it is for, estimated meter usage, requested assets, and every
requirement (dispatching_starter_kit/2_dispatch.md §10, R10). Time-based,
not identity-based — the one rule in doc 5 §4.5 that is about the record's
own state rather than the actor's relationship to it, so it lives here
rather than in the permission system."""

from __future__ import annotations

from app.events.models.details.dispatching import DispatchWorkflowStatus

LOCKED_STATUSES = frozenset(
    {
        DispatchWorkflowStatus.PLANNED,
        DispatchWorkflowStatus.ALTERNATE_RESOLUTION,
        DispatchWorkflowStatus.REJECTED,
    }
)

#: Always editable regardless of lock state (doc 2 §10) — title, description,
#: priority, activity_location, names_free_text, comments, attachments. None
#: of these change what was decided against.
ALWAYS_EDITABLE_FIELDS = frozenset(
    {"title", "description", "priority", "activity_location", "names_free_text"}
)


class IntentLockPolicy:
    @classmethod
    def is_locked(cls, dispatch) -> bool:
        return dispatch.workflow_status in LOCKED_STATUSES

    @classmethod
    def is_fully_editable(cls, dispatch) -> bool:
        return dispatch.workflow_status not in LOCKED_STATUSES

    @classmethod
    def check_editable(cls, *, dispatch, fields: set[str] | None = None) -> None:
        """Raises if intent is locked. ``fields``, when given, is checked
        against ALWAYS_EDITABLE_FIELDS so a caller updating only those may
        proceed even on a locked dispatch."""
        if dispatch.workflow_status not in LOCKED_STATUSES:
            return
        if fields is not None and fields.issubset(ALWAYS_EDITABLE_FIELDS):
            return
        raise ValueError(
            f"Intent is locked — dispatch is '{dispatch.workflow_status}'. Raise a "
            "new dispatch linked via previous_dispatch instead."
        )
