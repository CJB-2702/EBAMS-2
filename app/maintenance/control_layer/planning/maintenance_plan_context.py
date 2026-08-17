"""Context: entry point for control logic around one MaintenancePlan id —
activation lifecycle and maintenance-event generation from the plan's
template."""

from __future__ import annotations

from django.utils import timezone

from app.maintenance.models.planning.maintenance_plan import MaintenancePlan, PlanStatus


class MaintenancePlanContext:
    def __init__(self, maintenance_plan_id: int) -> None:
        self.maintenance_plan_id = maintenance_plan_id
        self._plan: MaintenancePlan | None = None

    @property
    def maintenance_plan(self) -> MaintenancePlan:
        if self._plan is None:
            self._plan = MaintenancePlan.objects.select_related(
                "template_action_set", "asset_class", "asset_model", "domain"
            ).get(pk=self.maintenance_plan_id, deleted_at__isnull=True)
        return self._plan

    def refresh(self) -> None:
        self._plan = None

    @property
    def is_active(self) -> bool:
        return self.maintenance_plan.status == PlanStatus.ACTIVE

    def activate(self, *, actor=None) -> MaintenancePlan:
        plan = self.maintenance_plan
        plan.status = PlanStatus.ACTIVE
        plan.updated_by = actor
        plan.save(update_fields=["status", "updated_by", "updated_at"])
        self.refresh()
        return plan

    def deactivate(self, *, actor=None) -> MaintenancePlan:
        plan = self.maintenance_plan
        plan.status = PlanStatus.INACTIVE
        plan.updated_by = actor
        plan.save(update_fields=["status", "updated_by", "updated_at"])
        self.refresh()
        return plan

    def create_maintenance_event(self, *, asset_id: int, event_start=None, actor=None):
        """Instantiate a live MaintenanceDetail from this plan's template — a
        thin pass-through to MaintenanceFactory, which owns the atomic
        expansion cascade (R2)."""
        from app.maintenance.control_layer.maintenance_factory import MaintenanceFactory

        plan = self.maintenance_plan
        return MaintenanceFactory.create_from_template(
            template_action_set_id=plan.template_action_set_id,
            domain_id=plan.domain_id,
            asset_id=asset_id,
            maintenance_plan_id=plan.pk,
            event_start=event_start or timezone.now(),
            actor=actor,
        )
