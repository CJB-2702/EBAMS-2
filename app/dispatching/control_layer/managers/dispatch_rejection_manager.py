"""Manager: records a rejection on the dispatch header — terminal, reason
required (dispatching_starter_kit/2_dispatch.md §9, R9). There is no
rejection record; the fields live on DispatchingDetail itself."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.dispatching.control_layer.guards.dispatch_state_guard import (
    DispatchTransitionStateMachine,
)
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.events.models.details.dispatching import DispatchWorkflowStatus, RejectionCategory

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchRejectionManager:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def reject(
        self,
        *,
        reason: str,
        category: str,
        alternative_suggestion: str = "",
        can_resubmit: bool = True,
        resubmit_after=None,
        actor: "AbstractUser",
    ):
        if not (reason or "").strip():
            raise ValueError("A rejection reason is required.")
        if category not in RejectionCategory.values:
            raise ValueError(f"'{category}' is not a valid rejection category.")

        verdict = DispatchTransitionStateMachine.check(
            from_status=self.dispatch.workflow_status, to_status=DispatchWorkflowStatus.REJECTED
        )
        if not verdict.allowed:
            raise ValueError(verdict.reason)

        dispatch = self.dispatch
        with transaction.atomic():
            dispatch.workflow_status = DispatchWorkflowStatus.REJECTED
            dispatch.rejection_reason = reason
            dispatch.rejection_category = category
            dispatch.rejected_by = actor
            dispatch.rejected_at = timezone.now()
            dispatch.alternative_suggestion = alternative_suggestion
            dispatch.can_resubmit = can_resubmit
            dispatch.resubmit_after = resubmit_after
            dispatch.updated_by = actor
            dispatch.save()

        self._ctx._narrate(DispatchNarrator.rejected(actor=actor, reason=reason, category=category))
        self._ctx.refresh()
        return self.dispatch
