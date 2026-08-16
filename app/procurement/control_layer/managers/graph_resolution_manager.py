"""Manager: the human-judgment columns on GraphSummary.

THE ONLY WRITE PATH IN THE GRAPH SURFACES. Every other column on GraphSummary
is derived and written exclusively by GraphSummaryManager.recalculate(); these
three are the exact inverse — written only here, and never touched by
recalculate().

    resolution_state    has a person ruled on this graph?
    manually_flagged    does somebody want eyes on it?
    priority            how urgent is the underlying work?

WHY THE INVERSION EXISTS. A derived state answers "does the arithmetic
currently balance", which flips back the instant anything changes. It cannot
express "I looked at this and I am finished with it". Without that, a
legitimately-permanently-imbalanced graph — a vendor overshipped 12 against a
demand for 10, everything was accepted, the business is done — is immortal
noise in every filtered list, which is the failure mode that kills a list
nobody can ever work down.

The danger this class exists to contain is that the surrounding convention is
so uniform that the natural assumption ("everything on GraphSummary is
derived") silently destroys user input on the next unrelated allocation. That
is why these live behind their own manager rather than being three more
assignments inside recalculate()'s update_fields.
"""

from __future__ import annotations

from app.procurement.models import (
    GraphResolutionState,
    GraphSummary,
)


class GraphResolutionManager:
    """Writes the three human columns on a GraphSummary. Nothing else does."""

    # ------------------------------------------------------------------ #
    # Resolution
    # ------------------------------------------------------------------ #

    @classmethod
    def set_resolution(
        cls, *, graph_id: int, resolution_state: str, actor=None
    ) -> GraphSummary:
        """Record a human ruling on this graph.

        OPEN            nobody has ruled yet (the default, and the reset value)
        RESOLVED        this got handled
        ACCEPTED_AS_IS  permanently lopsided, and that is fine

        The two non-OPEN values are kept distinct because they mean different
        things to the next reader: "this got fixed" versus "this will never
        balance and does not need to".
        """
        if resolution_state not in GraphResolutionState.values:
            raise ValueError(f"Not a resolution state: {resolution_state!r}")

        summary = GraphSummary.objects.get(pk=graph_id)
        summary.resolution_state = resolution_state
        summary.updated_by = actor
        summary.save(update_fields=["resolution_state", "updated_by", "updated_at"])
        return summary

    # ------------------------------------------------------------------ #
    # Flag and priority
    # ------------------------------------------------------------------ #

    @classmethod
    def set_flag(cls, *, graph_id: int, flagged: bool, actor=None) -> GraphSummary:
        """Raise or clear the "somebody wants eyes on this" marker."""
        summary = GraphSummary.objects.get(pk=graph_id)
        summary.manually_flagged = flagged
        summary.updated_by = actor
        summary.save(update_fields=["manually_flagged", "updated_by", "updated_at"])
        return summary

    @classmethod
    def set_priority(
        cls, *, graph_id: int, priority: str | None, actor=None
    ) -> GraphSummary:
        """Rank the underlying work, or clear the ranking with None.

        Reuses DemandPriority rather than inventing a parallel vocabulary — a
        word meaning two things in one codebase is a standing hazard here.
        None is a real value meaning "nobody has ranked this", deliberately not
        defaulted to medium.
        """
        summary = GraphSummary.objects.get(pk=graph_id)
        summary.priority = priority or None
        summary.updated_by = actor
        summary.save(update_fields=["priority", "updated_by", "updated_at"])
        return summary

    # ------------------------------------------------------------------ #
    # Merge and split survival
    # ------------------------------------------------------------------ #

    @classmethod
    def carry_through_merge(
        cls, *, survivor_id: int, absorbed_resolution: dict, actor=None
    ) -> GraphSummary:
        """Apply the survival principle when graph B is absorbed into graph A.

        THE PRINCIPLE, from which all of this follows:

            Anything derived from a graph's CONFIGURATION clears when the
            configuration changes. Anything expressing HUMAN JUDGMENT ABOUT
            IMPORTANCE propagates.

        resolution_state is a statement about a specific set of nodes — "I
        looked at this and it is finished". When nodes join or leave, the thing
        that was looked at no longer exists and the statement has no referent,
        so it resets. Priority and flagging are about the underlying work — the
        part, the urgency, the fact that somebody wants eyes on it — and
        restructuring does not invalidate any of that, so they survive.

        KEEPING THE SURVIVOR'S RESOLUTION WAS REJECTED. A resolved graph would
        silently absorb an unresolved one and stay resolved, making the
        absorbed graph's problem vanish from every list without anyone
        addressing it. That is a correctness failure wearing a convenience
        costume.

        The cost is real and should not be hidden from users: a Buyer who
        resolves a graph may find it OPEN again after an unrelated allocation,
        with no explanation they can see. That is the correct behaviour — the
        graph genuinely changed — but it will feel arbitrary from outside,
        which is why the caller is expected to write a line to the surviving
        members' activity trail saying so.
        """
        summary = GraphSummary.objects.get(pk=survivor_id)
        summary.resolution_state = GraphResolutionState.OPEN
        summary.manually_flagged = summary.manually_flagged or bool(
            absorbed_resolution.get("manually_flagged")
        )
        summary.priority = cls._more_urgent(
            summary.priority, absorbed_resolution.get("priority")
        )
        summary.updated_by = actor
        summary.save(
            update_fields=[
                "resolution_state",
                "manually_flagged",
                "priority",
                "updated_by",
                "updated_at",
            ]
        )
        return summary

    @classmethod
    def carry_through_split(
        cls, *, origin_id: int, new_graph_id: int, actor=None
    ) -> None:
        """Apply the survival principle when graph A splits into A and B.

        Both halves reset to OPEN — neither is the graph that was looked at.
        Flag and priority are COPIED to both rather than picked between: the
        work was important before the split and both halves inherit that, and
        there is no basis for deciding which half kept the importance.
        """
        origin = GraphSummary.objects.get(pk=origin_id)
        carried_flag = origin.manually_flagged
        carried_priority = origin.priority

        for graph_id in (origin_id, new_graph_id):
            summary = GraphSummary.objects.get(pk=graph_id)
            summary.resolution_state = GraphResolutionState.OPEN
            summary.manually_flagged = carried_flag
            summary.priority = carried_priority
            summary.updated_by = actor
            summary.save(
                update_fields=[
                    "resolution_state",
                    "manually_flagged",
                    "priority",
                    "updated_by",
                    "updated_at",
                ]
            )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    #: Rank order for picking the more urgent of two priorities on a merge.
    #: None sorts lowest — an unranked graph never outranks a ranked one.
    _PRIORITY_RANK: dict[str | None, int] = {
        None: 0,
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4,
    }

    @classmethod
    def _more_urgent(cls, a: str | None, b: str | None) -> str | None:
        return a if cls._PRIORITY_RANK.get(a, 0) >= cls._PRIORITY_RANK.get(b, 0) else b
