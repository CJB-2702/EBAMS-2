"""Manager: assignment sub-domain for one MaintenanceDetail
(MaintenanceContext.assignment_manager)."""

from __future__ import annotations

from django.contrib.auth import get_user_model


class MaintenanceAssignmentManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    @property
    def is_assigned(self) -> bool:
        return self._ctx.maintenance_detail.assigned_user_id is not None

    def assign(self, *, assigned_user, assigned_by) -> None:
        User = get_user_model()
        if not User.objects.filter(pk=assigned_user.pk, is_active=True).exists():
            raise ValueError(f"User {assigned_user.pk} not found or not active.")
        detail = self._ctx.maintenance_detail
        detail.assigned_user = assigned_user
        detail.assigned_by = assigned_by
        detail.updated_by = assigned_by
        detail.save(
            update_fields=["assigned_user", "assigned_by", "updated_by", "updated_at"]
        )
        self._ctx.refresh()

    def auto_assign(self, *, actor) -> bool:
        """Assign to `actor` only if nobody is assigned yet — a side effect of the
        first person to touch the event, never overrides an existing assignment."""
        if actor is None or self.is_assigned:
            return False
        detail = self._ctx.maintenance_detail
        detail.assigned_user = actor
        detail.assigned_by = actor
        detail.updated_by = actor
        detail.save(
            update_fields=["assigned_user", "assigned_by", "updated_by", "updated_at"]
        )
        self._ctx.refresh()
        return True
