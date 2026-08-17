"""Guard type: Policy. Gates MaintenanceContext.complete() against R4's
completion truth table:

    ALL Action rows must be Complete or Skipped, AND
    ALL MaintenanceBlocker rows must be resolved (end_date set), AND
    ALL AssetLimitationRecord rows must be closed (end_time set).

All three must pass — there is no partial-completion path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.maintenance.models.action import ActionStatus

#: Action statuses that satisfy R4's "done" requirement for completion purposes.
TERMINAL_ACTION_STATUSES = frozenset({ActionStatus.COMPLETE, ActionStatus.SKIPPED})


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
                f"{len(unfinished)} action(s) are not yet Complete or Skipped."
            )

        active_blockers = struct.active_blockers
        if active_blockers:
            reasons.append(f"{len(active_blockers)} blocker(s) are still active.")

        active_limitations = struct.active_limitation_records
        if active_limitations:
            reasons.append(
                f"{len(active_limitations)} asset limitation record(s) are still open."
            )

        return CompletionVerdict(allowed=not reasons, reasons=reasons)
