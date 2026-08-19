"""Orchestrator: evaluates MaintenancePlan schedules and finds assets due for
maintenance.

Calendar-frequency plans (delta_days since last completed service) are fully
evaluated. Meter-frequency plans are recognized but not numerically evaluated
in this build — see PlanningResult usage and the module docstring on
plan_for() for why (meter comparison needs assets.MeterHistory, which this
planner deliberately does not reach into yet).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from app.events.models.event import EventStatus
from app.maintenance.models.planning.maintenance_plan import (
    MaintenancePlan,
    PlanFrequencyType,
    PlanStatus,
)


@dataclass
class PlanningResult:
    maintenance_plan_id: int
    asset_id: int
    needs_maintenance: bool
    reason: str = ""
    recommended_start: datetime | None = None


class MaintenancePlanner:
    @classmethod
    def plan_all_active_plans(cls) -> list[PlanningResult]:
        results: list[PlanningResult] = []
        for plan in MaintenancePlan.objects.filter(
            status=PlanStatus.ACTIVE, deleted_at__isnull=True
        ):
            results.extend(cls.plan_for(plan))
        return results

    @classmethod
    def plan_for(cls, plan: MaintenancePlan) -> list[PlanningResult]:
        if plan.frequency_type == PlanFrequencyType.CALENDAR:
            return cls._plan_calendar(plan)
        # Meter-based due dates require comparing MeterHistory readings against
        # delta_m1..delta_m4 per meter index. Deferred — not implemented here.
        return []

    @classmethod
    def _plan_calendar(cls, plan: MaintenancePlan) -> list[PlanningResult]:
        results: list[PlanningResult] = []
        if not plan.delta_days:
            return results
        for asset in cls._matching_assets(plan):
            if cls._has_duplicate_event(plan_id=plan.pk, asset_id=asset.pk):
                continue
            last_completed = (
                asset.maintenance_details.filter(
                    maintenance_plan_id=plan.pk,
                    status=EventStatus.COMPLETE,
                    deleted_at__isnull=True,
                )
                .order_by("-event_end")
                .first()
            )
            due_at = (
                last_completed.event_end + timedelta(days=plan.delta_days)
                if last_completed and last_completed.event_end
                else timezone.now()
            )
            if due_at <= timezone.now():
                results.append(
                    PlanningResult(
                        maintenance_plan_id=plan.pk,
                        asset_id=asset.pk,
                        needs_maintenance=True,
                        reason=f"Due — {plan.delta_days} days since last completed service.",
                        recommended_start=due_at,
                    )
                )
        return results

    @staticmethod
    def _matching_assets(plan: MaintenancePlan):
        from app.assets.models.core.asset import Asset

        # Asset has no soft-delete column — is_active is the liveness filter.
        qs = Asset.objects.filter(is_active=True, asset_class_id=plan.asset_class_id)
        if plan.asset_models.exists():
            qs = qs.filter(model_id__in=plan.asset_models.all())
        return qs

    @staticmethod
    def _has_duplicate_event(*, plan_id: int, asset_id: int) -> bool:
        from app.events.models.details.maintenance import MaintenanceDetail

        return MaintenanceDetail.objects.filter(
            maintenance_plan_id=plan_id,
            asset_id=asset_id,
            status__in=(EventStatus.PLANNED, EventStatus.IN_PROGRESS),
            deleted_at__isnull=True,
        ).exists()

    @classmethod
    def create_events_from_results(cls, results: list[PlanningResult], *, actor=None) -> list:
        from app.maintenance.control_layer.planning.maintenance_plan_context import (
            MaintenancePlanContext,
        )

        created = []
        for result in results:
            if not result.needs_maintenance:
                continue
            if cls._has_duplicate_event(
                plan_id=result.maintenance_plan_id, asset_id=result.asset_id
            ):
                continue
            context = MaintenancePlanContext(result.maintenance_plan_id)
            detail = context.create_maintenance_event(
                asset_id=result.asset_id,
                event_start=result.recommended_start,
                actor=actor,
            )
            created.append(detail)
        return created
