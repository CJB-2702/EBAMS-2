"""The ONLY writer of PartDemand's four snapshot columns.

There is no code path that writes a snapshot column without also writing its
PartDemandUpdate journal row. The two move together, in one transaction, from
this one class. Snapshot columns are a cache; if they ever disagree with the
journal, the journal wins and the snapshots are rebuildable from it.

    transition(dimension, to_stage, actor, notes)
      |- PartDemandTransitionStateMachine.check()   legal? gated? (D9-D11)
      |                                            undecidable -> allow + flag (D13)
      |- INSERT PartDemandUpdate
      |- UPDATE PartDemand.<axis>
      '- DemandCompletionHandler.check()            may recurse once (D43)
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from app.procurement.control_layer.errors import TransitionRefused
from app.procurement.control_layer.guards.part_demand_state_guard import (
    PartDemandTransitionStateMachine,
    TransitionVerdict,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import DIMENSION_FIELDS, PartDemandUpdate


@dataclass(frozen=True)
class TransitionResult:
    """``moved`` False with ``refusal`` set means a gate declined.

    Propagation callers use this to skip a demand without failing the whole
    workflow — placing a PO must not fail because one of its demands is still
    unapproved (the exact case D42's opt-out exists to create).
    """

    moved: bool
    update: PartDemandUpdate | None = None
    refusal: str = ""
    flagged: bool = False


class PartDemandStateManager:
    @classmethod
    def transition(
        cls,
        *,
        demand,
        dimension: str,
        to_stage: str,
        actor=None,
        notes: str = "",
        is_system_generated: bool = False,
        raise_on_refusal: bool = True,
        allow_same_stage: bool = False,
        commit: bool = True,
    ) -> TransitionResult:
        """Move one axis. Returns a result rather than a bare bool so callers
        can distinguish "refused by a gate" from "nothing to do".

        `allow_same_stage` records a RESTATEMENT: a real event that leaves the
        axis where it already was, journalled with previous_stage == stage.
        Normally the state machine refuses that as a no-op, and it is right to
        — but a second partial handover against a demand already sitting in
        Partially Issued is not a no-op, it is another set of parts crossing
        the counter, and refusing it would make repeat partial issuance
        impossible. Only a caller that knows an event actually happened may
        pass it; it never bypasses a gate, only the same-stage check.
        """
        field = DIMENSION_FIELDS.get(dimension)
        if field is None:
            raise ValueError(f"Unknown demand dimension: {dimension!r}")

        from_stage = getattr(demand, field)

        if allow_same_stage and from_stage == to_stage:
            verdict = TransitionVerdict(allowed=True)
        else:
            verdict = PartDemandTransitionStateMachine.check(
                demand=demand,
                dimension=dimension,
                from_stage=from_stage,
                to_stage=to_stage,
            )
        if not verdict.allowed:
            if raise_on_refusal:
                raise TransitionRefused([verdict.reason])
            return TransitionResult(moved=False, refusal=verdict.reason)

        text = notes or PartDemandNarrator.transitioned(
            dimension=dimension, from_stage=from_stage, to_stage=to_stage
        )
        if verdict.flagged and verdict.reason:
            # Fail-open transitions carry their reason into the journal, so the
            # review queue explains itself without a second lookup.
            text = f"{text} [flagged: {verdict.reason}]"

        def _write() -> TransitionResult:
            update = PartDemandUpdate.objects.create(
                part_demand=demand,
                dimension=dimension,
                stage=to_stage,
                previous_stage=from_stage,
                actor=actor,
                is_system_generated=is_system_generated,
                notes=text,
                flagged_for_review=verdict.flagged,
                created_by=actor,
                updated_by=actor,
            )
            setattr(demand, field, to_stage)
            demand.updated_by = actor
            demand.save(update_fields=[field, "updated_by", "updated_at"])

            # Imported here rather than at module scope: the handler calls back
            # into this manager, and a module-level import would be circular.
            from app.procurement.control_layer.handlers.demand_completion_handler import (
                DemandCompletionHandler,
            )

            DemandCompletionHandler.check(
                demand=demand, dimension=dimension, actor=actor
            )
            return TransitionResult(
                moved=True, update=update, flagged=verdict.flagged
            )

        if commit:
            with transaction.atomic():
                return _write()
        return _write()

    @classmethod
    def initialize(cls, *, demand, actor=None, commit: bool = True) -> list[PartDemandUpdate]:
        """Write the four initializing journal rows — one per axis, with
        previous_stage blank (R2).

        Four rows, not one. This is what makes the journal a complete account
        rather than a change log with an unexplained starting point.
        """

        def _write() -> list[PartDemandUpdate]:
            rows = []
            for dimension, field in DIMENSION_FIELDS.items():
                stage = getattr(demand, field)
                rows.append(
                    PartDemandUpdate(
                        part_demand=demand,
                        dimension=dimension,
                        stage=stage,
                        previous_stage="",
                        actor=actor,
                        is_system_generated=False,
                        notes=PartDemandNarrator.initialized(
                            dimension=dimension, stage=stage
                        ),
                        created_by=actor,
                        updated_by=actor,
                    )
                )
            return PartDemandUpdate.objects.bulk_create(rows)

        if commit:
            with transaction.atomic():
                return _write()
        return _write()
