"""Context: entry point for control logic around one dispatch id.

Owns the explicit lifecycle verbs (submit, take under review, request
fixes, resubmit, complete) directly; delegates rejection, cancellation,
requirements, demands, crew, and supersession to stable sub-managers.
Planned/AlternateResolution is never set here — DispatchStateDeriver
recomputes it after every line-item change (R8).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.domain_structs.dispatch_detail_struct import (
    DispatchDetailStruct,
)
from app.dispatching.control_layer.guards.dispatch_state_guard import (
    DispatchTransitionStateMachine,
)
from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.events.models.details.dispatching import DispatchingDetail, DispatchWorkflowStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchContext:
    def __init__(self, dispatch_id: int, actor: "AbstractUser") -> None:
        self.actor = actor
        self.struct = DispatchDetailStruct.load(dispatch_id=dispatch_id)

    @classmethod
    def from_struct(cls, struct: DispatchDetailStruct, actor: "AbstractUser") -> "DispatchContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        return ctx

    @property
    def dispatch(self) -> DispatchingDetail:
        return self.struct.dispatch

    def refresh(self) -> None:
        self.struct = DispatchDetailStruct.load(dispatch_id=self.dispatch.pk)

    # ------------------------------------------------------------------ #
    # Sub-managers
    # ------------------------------------------------------------------ #

    @property
    def requirements(self):
        from app.dispatching.control_layer.managers.requirement_manifest_editor import (
            RequirementManifestEditor,
        )

        return RequirementManifestEditor(self)

    @property
    def expenses(self):
        from app.dispatching.control_layer.managers.expense_manager import ExpenseManager

        return ExpenseManager(self)

    @property
    def demands(self):
        from app.dispatching.control_layer.managers.dispatch_demand_manager import (
            DispatchDemandManager,
        )

        return DispatchDemandManager(self)

    @property
    def crew(self):
        from app.dispatching.control_layer.managers.crew_roster_manager import (
            CrewRosterManager,
        )

        return CrewRosterManager(self)

    @property
    def rejection(self):
        from app.dispatching.control_layer.managers.dispatch_rejection_manager import (
            DispatchRejectionManager,
        )

        return DispatchRejectionManager(self)

    @property
    def cancellation(self):
        from app.dispatching.control_layer.managers.dispatch_cancellation_orchestrator import (
            DispatchCancellationOrchestrator,
        )

        return DispatchCancellationOrchestrator(self)

    @property
    def supersession(self):
        from app.dispatching.control_layer.managers.dispatch_supersession_manager import (
            DispatchSupersessionManager,
        )

        return DispatchSupersessionManager(self)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _narrate(self, text: str) -> None:
        from app.events.control_layer.event_context import EventContext

        EventContext(self.dispatch.pk, self.actor).add_comment({"content": text}, is_human_made=False)

    def _transition(self, *, to_status: str) -> None:
        verdict = DispatchTransitionStateMachine.check(
            from_status=self.dispatch.workflow_status, to_status=to_status
        )
        if not verdict.allowed:
            raise ValueError(verdict.reason)

    # ------------------------------------------------------------------ #
    # Intent
    # ------------------------------------------------------------------ #

    def update_intent(self, **fields) -> DispatchingDetail:
        IntentLockPolicy.check_editable(dispatch=self.dispatch, fields=set(fields))
        dispatch = self.dispatch
        update_fields: list[str] = []
        for field_name, value in fields.items():
            setattr(dispatch, field_name, value)
            update_fields.append(field_name)
        if update_fields:
            dispatch.updated_by = self.actor
            dispatch.save(update_fields=update_fields + ["updated_by", "updated_at"])
        self.refresh()
        return self.dispatch

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def submit(self, *, candidate_asset_ids: list[int] | None = None) -> DispatchingDetail:
        from django.utils import timezone

        self._transition(to_status=DispatchWorkflowStatus.SUBMITTED)
        dispatch = self.dispatch
        with transaction.atomic():
            dispatch.workflow_status = DispatchWorkflowStatus.SUBMITTED
            dispatch.submitted_at = timezone.now()
            dispatch.updated_by = self.actor
            dispatch.save(update_fields=["workflow_status", "submitted_at", "updated_by", "updated_at"])
        self._narrate(DispatchNarrator.submitted(actor=self.actor))
        self.refresh()

        if candidate_asset_ids:
            from app.dispatching.control_layer.managers.requested_asset_auto_reserver import (
                RequestedAssetAutoReserver,
            )

            RequestedAssetAutoReserver.reserve_free_assets(
                dispatch=self.dispatch, candidate_asset_ids=candidate_asset_ids, actor=self.actor
            )
            self.refresh()
        return self.dispatch

    def take_under_review(self) -> DispatchingDetail:
        self._transition(to_status=DispatchWorkflowStatus.UNDER_REVIEW)
        dispatch = self.dispatch
        dispatch.workflow_status = DispatchWorkflowStatus.UNDER_REVIEW
        dispatch.updated_by = self.actor
        dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])
        self._narrate(DispatchNarrator.taken_under_review(actor=self.actor))
        self.refresh()
        return self.dispatch

    def request_fixes(self, *, reason: str) -> DispatchingDetail:
        if not (reason or "").strip():
            raise ValueError("A reason is required to send a dispatch back for fixes.")
        self._transition(to_status=DispatchWorkflowStatus.FIXES_REQUESTED)
        dispatch = self.dispatch
        dispatch.workflow_status = DispatchWorkflowStatus.FIXES_REQUESTED
        dispatch.updated_by = self.actor
        dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])
        self._narrate(DispatchNarrator.fixes_requested(actor=self.actor, reason=reason))
        self.refresh()
        return self.dispatch

    def resubmit(self) -> DispatchingDetail:
        self._transition(to_status=DispatchWorkflowStatus.SUBMITTED)
        dispatch = self.dispatch
        dispatch.workflow_status = DispatchWorkflowStatus.SUBMITTED
        dispatch.updated_by = self.actor
        dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])
        self._narrate(DispatchNarrator.resubmitted(actor=self.actor))
        self.refresh()
        return self.dispatch

    def mark_completed(self) -> DispatchingDetail:
        self._transition(to_status=DispatchWorkflowStatus.COMPLETED)
        dispatch = self.dispatch
        dispatch.workflow_status = DispatchWorkflowStatus.COMPLETED
        dispatch.updated_by = self.actor
        dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])
        self._narrate(DispatchNarrator.completed(actor=self.actor))
        self.refresh()
        return self.dispatch
