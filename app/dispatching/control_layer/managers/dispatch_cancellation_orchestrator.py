"""Orchestrator: cross-boundary coordinator for cancelling a dispatch —
cancels its live reservations (carrying the dispatch's cancellation reason
onto each) and asks the demand hub to cancel unissued material demands,
never deciding what cancelling a demand means itself
(dispatching_starter_kit/2_dispatch.md §13, R13)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.dispatch_state_guard import (
    LIVE_RESERVATION_STATUSES,
    DispatchTransitionStateMachine,
)
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.events.models.details.dispatching import DispatchWorkflowStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchCancellationOrchestrator:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def cancel(self, *, reason: str, actor: "AbstractUser") -> dict:
        if not (reason or "").strip():
            raise ValueError("A cancellation reason is required.")

        verdict = DispatchTransitionStateMachine.check(
            from_status=self.dispatch.workflow_status, to_status=DispatchWorkflowStatus.CANCELLED
        )
        if not verdict.allowed:
            raise ValueError(verdict.reason)

        from app.dispatching.control_layer.reservation_context import ReservationContext

        cancelled_reservation_ids: list[int] = []
        for reservation in self.dispatch.reservations.filter(
            deleted_at__isnull=True, reservation_status__in=LIVE_RESERVATION_STATUSES
        ):
            ReservationContext(reservation.pk, actor).cancel(reason=reason)
            cancelled_reservation_ids.append(reservation.pk)

        from app.dispatching.control_layer.managers.dispatch_demand_manager import (
            DispatchDemandManager,
        )

        demand_results = DispatchDemandManager(self._ctx).cancel_all_unissued(
            actor=actor, reason=reason
        )

        dispatch = self.dispatch
        with transaction.atomic():
            dispatch.workflow_status = DispatchWorkflowStatus.CANCELLED
            dispatch.updated_by = actor
            dispatch.save(update_fields=["workflow_status", "updated_by", "updated_at"])

        self._ctx._narrate(DispatchNarrator.cancelled(actor=actor, reason=reason))
        self._ctx.refresh()
        return {
            "cancelled_reservation_ids": cancelled_reservation_ids,
            "demand_results": demand_results,
        }
