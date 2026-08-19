"""Guard type: Policy. Gates MaintenanceContext.complete() against R4's
completion truth table:

    ALL Action rows must be in a terminal state (Complete, Failed, or
    Skipped), AND
    ALL MaintenanceBlocker rows must be resolved (end_date set), AND
    ALL AssetLimitationRecord rows must be closed (end_time set), AND
    MaintenanceDetail.actual_billable_hours must be >= the sum of the
    individual Action.billable_hours values.

All four must pass — there is no partial-completion path.

The billable-hours check is a floor, not an equality: the event-level total
is allowed to exceed the per-action sum (see billable_hours_manager.py — a
technician's manual override is expected to run ahead of the calculated
sum), it just can never complete while it's short of it. Computed here
directly from struct rather than via BillableHoursManager, same as the other
three checks below never go through their own managers — this guard reads
structs, not contexts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.maintenance.control_layer.action_context import TERMINAL_STATUSES

#: Action statuses that satisfy R4's "done" requirement for completion purposes.
#
# Deliberately re-exported from ActionContext rather than redefined. This guard
# used to carry its own narrower set — {Complete, Skipped} — while
# ActionContext.TERMINAL_STATUSES has always included Failed. The two
# definitions disagreed, and the guard's was wrong: a failed step is SETTLED.
# The technician tried it, it did not work, and that outcome is recorded. There
# is no verb that moves it out of Failed except an explicit reopen, so treating
# Failed as unfinished left the event permanently uncompletable with no way for
# the technician to clear it — they would have had to lie and mark the step
# Complete or Skipped to close the job. Legacy agreed (see
# MaintenanceContext.all_actions_in_terminal_states: {Complete, Failed,
# Skipped}). "Every step reached an outcome" is the completion rule, not "every
# step succeeded".
TERMINAL_ACTION_STATUSES = TERMINAL_STATUSES


@dataclass(frozen=True)
class CompletionVerdict:
    allowed: bool
    reasons: list[str] = field(default_factory=list)


class MaintenanceCompletionPolicy:
    """Policy: may this MaintenanceDetail be marked Complete right now?"""

    @classmethod
    def check(cls, *, struct) -> CompletionVerdict:
        reasons: list[str] = []

        unfinished = [a for a in struct.actions if a.status not in TERMINAL_ACTION_STATUSES]
        if unfinished:
            reasons.append(
                f"{len(unfinished)} action(s) have not reached an outcome "
                f"(Complete, Failed, or Skipped)."
            )

        active_blockers = struct.active_blockers
        if active_blockers:
            reasons.append(f"{len(active_blockers)} blocker(s) are still active.")

        active_limitations = struct.active_limitation_records
        if active_limitations:
            reasons.append(
                f"{len(active_limitations)} asset limitation record(s) are still open."
            )

        calculated_hours = sum(a.billable_hours or 0 for a in struct.actions)
        actual_hours = struct.maintenance_detail.actual_billable_hours or 0
        if actual_hours < calculated_hours:
            reasons.append(
                f"Actual billable hours ({actual_hours:.2f}) is less than the "
                f"sum of the individual actions' billable hours ({calculated_hours:.2f})."
            )

        return CompletionVerdict(allowed=not reasons, reasons=reasons)
