"""Guard type: Policy. D6's hard-delete-only-while-untouched decision.

THIS GUARD CHECKS ONLY THIS APP'S OWN TABLES (D7). It looks at
PurchaseOrderDemandLink and PartDemandUpdate. That is the whole check. It does
not know inventory exists, does not know Maintenance or Dispatching will exist,
and imports nothing from any of them.

Cross-app protection is free: every consumer app owns its own link table with a
PROTECT FK to PartDemand (inventory.PartIssue already does), so Django raises
ProtectedError before this guard is even consulted.

This is the direct fix for the legacy DemandOriginResolver, which reached into
maintenance/dispatching model internals behind try/except ImportError guards to
answer the same question. The FK answers it with no imports at all.

Despite the Policy suffix this is a business rule, not authorization —
permission checks are deferred to the presentation layer for this build.
"""

from __future__ import annotations

from dataclasses import dataclass

#: A freshly created demand has exactly one initializing journal row per axis.
INITIALIZING_JOURNAL_ROW_COUNT = 4


@dataclass(frozen=True)
class DeletionVerdict:
    """hard_delete False means soft-delete instead. Never a refusal: a demand
    is always removable one way or the other."""

    hard_delete: bool
    reason: str


class PartDemandDeletionPolicy:
    @classmethod
    def decide(cls, *, demand) -> DeletionVerdict:
        allocation_count = demand.allocations.count()
        if allocation_count:
            return DeletionVerdict(
                hard_delete=False,
                reason=(
                    f"{allocation_count} purchase order allocation(s) exist — "
                    f"deactivating instead of deleting."
                ),
            )

        journal_count = demand.updates.count()
        if journal_count > INITIALIZING_JOURNAL_ROW_COUNT:
            return DeletionVerdict(
                hard_delete=False,
                reason=(
                    "The demand has journal activity beyond creation — "
                    "deactivating instead of deleting."
                ),
            )

        return DeletionVerdict(
            hard_delete=True, reason="Untouched since creation — safe to hard delete."
        )
