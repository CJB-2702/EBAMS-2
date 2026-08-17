"""Manager: billable-hours sub-domain for one MaintenanceDetail
(MaintenanceContext.billable_hours_manager).

actual_billable_hours is a technician-editable override; calculated_hours is
the live sum of each child Action's billable_hours. The two are allowed to
disagree — get_warning() surfaces it, nothing enforces agreement.
"""

from __future__ import annotations


class BillableHoursManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    @property
    def calculated_hours(self) -> float:
        return sum(a.billable_hours or 0 for a in self._ctx.struct.actions)

    @property
    def actual_hours(self) -> float | None:
        return self._ctx.maintenance_detail.actual_billable_hours

    def auto_update_if_greater(self, *, actor=None) -> bool:
        """Called after an action billable-hours edit — raises the event total to
        match the calculated sum, never lowers it. A technician's manual override
        always wins on the way down."""
        calculated = self.calculated_hours
        current = self.actual_hours or 0
        if calculated <= current:
            return False
        detail = self._ctx.maintenance_detail
        detail.actual_billable_hours = calculated
        detail.updated_by = actor
        detail.save(update_fields=["actual_billable_hours", "updated_by", "updated_at"])
        self._ctx.refresh()
        return True

    def set_actual_hours(self, *, value: float, actor=None) -> None:
        if value < 0:
            raise ValueError("Billable hours must be non-negative.")
        detail = self._ctx.maintenance_detail
        detail.actual_billable_hours = value
        detail.updated_by = actor
        detail.save(update_fields=["actual_billable_hours", "updated_by", "updated_at"])
        self._ctx.refresh()

    def sync_to_calculated(self, *, actor=None) -> None:
        self.set_actual_hours(value=self.calculated_hours, actor=actor)

    def get_warning(self) -> str | None:
        calculated = self.calculated_hours
        actual = self.actual_hours
        if actual is None:
            return None
        if actual < calculated:
            return (
                f"Actual billable hours ({actual:.2f}) is less than the "
                f"calculated sum ({calculated:.2f})."
            )
        if calculated > 0 and actual > calculated * 4:
            return (
                f"Actual billable hours ({actual:.2f}) is more than 4x the "
                f"calculated sum ({calculated:.2f})."
            )
        return None
