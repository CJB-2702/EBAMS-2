"""Context: the entry point for control logic around one demand_id.

Every domain verb on a demand lives here. Nothing writes a snapshot column any
other way — each verb below is a call into PartDemandStateManager, which is the
single write path for all four axes.

Domain verbs, not CRUD verbs: approve(), cancel(), record_issuance() — never
update_state().
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.domain_structs.part_demand_struct import (
    PartDemandStruct,
)
from app.procurement.control_layer.errors import TransitionRefused
from app.procurement.control_layer.guards.part_demand_deletion_guard import (
    DeletionVerdict,
    PartDemandDeletionPolicy,
)
from app.procurement.control_layer.guards.part_demand_substitution_guard import (
    PartDemandSubstitutionPolicy,
)
from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.managers.part_demand_issuance_manager import (
    PartDemandIssuanceManager,
)
from app.procurement.control_layer.managers.part_demand_quantity_manager import (
    PartDemandQuantityManager,
)
from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
    TransitionResult,
)
from app.procurement.models import (
    PURCHASING_STATE_UNSET,
    DemandDimension,
    DemandState,
    PartDemand,
)


class PartDemandContext:
    def __init__(self, demand_id: int) -> None:
        self.demand_id = demand_id
        self._demand: PartDemand | None = None

    @classmethod
    def from_struct(cls, struct: PartDemandStruct) -> "PartDemandContext":
        context = cls(struct.demand_id)
        return context

    @property
    def demand(self) -> PartDemand:
        if self._demand is None:
            self._demand = PartDemand.objects.select_related("part", "domain").get(
                pk=self.demand_id
            )
        return self._demand

    def struct(self) -> PartDemandStruct:
        return PartDemandStruct.load(demand_id=self.demand_id)

    # ------------------------------------------------------------------ #
    # demand_state
    # ------------------------------------------------------------------ #

    def approve(self, *, actor=None, notes: str = "", commit: bool = True) -> TransitionResult:
        """Confirm the need is legitimate, unblocking purchasing (Gate 1).

        Approval authorizes purchasing to begin; it is not itself a purchasing
        decision, and nothing here moves purchasing_state.

        In practice this is usually reached as a side effect of a Buyer's PO
        link rather than an explicit Approver action (D42) — but the explicit
        path is what exists when someone deliberately wants the strict process,
        so it must not be deleted for being rare.
        """
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.APPROVED,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    def reject(self, *, actor=None, notes: str = "", commit: bool = True) -> TransitionResult:
        """Decline the demand. notes stays optional even here (D15) — a
        required reason field would be filled with 'n/a' within a week."""
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.REJECTED,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    def resubmit(self, *, actor=None, notes: str = "", commit: bool = True) -> TransitionResult:
        """Rejected -> Required. SAME ROW: no new PartDemand, no reopen action,
        no versioning (M5). The journal carries the full loop, however many
        times it happens."""
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.REQUIRED,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    def mark_required(self, *, actor=None, notes: str = "", commit: bool = True) -> TransitionResult:
        """Projected -> Required: a forecasted need became real, typically when
        a worker starts the task it is attached to."""
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.REQUIRED,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    def cancel(self, *, actor=None, notes: str = "", commit: bool = True) -> TransitionResult:
        """Close out a need that no longer exists.

        Requester or Approver only — a Buyer de-links instead (D4). Gate 2
        (D10) refuses this while a linked PO is still active, naming the PO
        that must be cancelled first. The refusal is doing its job: cancelling
        the order before the request behind it is how real purchasing works.
        """
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.DEMAND,
            to_stage=DemandState.CANCELLED,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    # ------------------------------------------------------------------ #
    # purchasing_state / shipment_state
    # ------------------------------------------------------------------ #

    def set_purchasing_state(
        self,
        *,
        to_stage: str,
        actor=None,
        notes: str = "",
        is_system_generated: bool = False,
        raise_on_refusal: bool = True,
        commit: bool = True,
    ) -> TransitionResult:
        """Move the money axis. Mostly driven by PO status propagation (D40)
        rather than called directly."""
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.PURCHASING,
            to_stage=to_stage,
            actor=actor,
            notes=notes,
            is_system_generated=is_system_generated,
            raise_on_refusal=raise_on_refusal,
            commit=commit,
        )

    def clear_purchasing_state(
        self, *, actor=None, notes: str = "", commit: bool = True
    ) -> TransitionResult:
        """D56: return the demand to 'no purchasing decision has been made'.

        The only backward move in this axis, and this is the only path that
        produces it — a PO line was cancelled, so the thing that was going to
        buy this demand is gone. demand_state is deliberately untouched: the
        need may still be real and buyable elsewhere.
        """
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.PURCHASING,
            to_stage=PURCHASING_STATE_UNSET,
            actor=actor,
            notes=notes,
            is_system_generated=True,
            raise_on_refusal=False,
            commit=commit,
        )

    def advance_shipment(
        self,
        *,
        to_stage: str,
        actor=None,
        notes: str = "",
        is_system_generated: bool = False,
        raise_on_refusal: bool = True,
        commit: bool = True,
    ) -> TransitionResult:
        """Move the physical axis.

        The middle stretch (Production in Progress -> Vendor Prepared to Ship
        -> Shipped) is advanced manually by the Buyer as vendor updates arrive;
        nothing computes it in this build. Backordered is an everyday
        occurrence, not an edge case (D44).
        """
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.SHIPMENT,
            to_stage=to_stage,
            actor=actor,
            notes=notes,
            is_system_generated=is_system_generated,
            raise_on_refusal=raise_on_refusal,
            commit=commit,
        )

    def set_issuance_state(
        self,
        *,
        to_stage: str,
        actor=None,
        notes: str = "",
        commit: bool = True,
    ) -> TransitionResult:
        """Move the issuance axis WITHOUT recording a quantity.

        Backs the edit page's "Issuance" status-update action
        (part_demand_workflows.md §2.3): flip to/from
        IssuanceState.ISSUED_RECONCILIATION_REQUIRED. Deliberately distinct
        from record_issuance() below — that one takes a net quantity and is
        only ever called from app/inventory/. This one never touches
        issued_qty, because the point of this state is that the movement is
        unreconciled; recording a number here would be a claim, not a record.
        """
        return PartDemandStateManager.transition(
            demand=self.demand,
            dimension=DemandDimension.ISSUANCE,
            to_stage=to_stage,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    # ------------------------------------------------------------------ #
    # issuance_state — the inward seam from app/inventory/ (D12)
    # ------------------------------------------------------------------ #

    def record_issuance(
        self,
        *,
        net_issued_qty: Decimal,
        to_stage: str,
        actor=None,
        notes: str = "",
        commit: bool = True,
    ) -> TransitionResult:
        """Called from app/inventory/, never from a form in this app.

        Takes the net quantity AS AN ARGUMENT — it does not query PartIssue to
        compute it, because procurement may not look at inventory. See
        PartDemandIssuanceManager for the full statement of that cost.
        """
        return PartDemandIssuanceManager.record(
            demand=self.demand,
            net_issued_qty=net_issued_qty,
            to_stage=to_stage,
            actor=actor,
            notes=notes,
            commit=commit,
        )

    # ------------------------------------------------------------------ #
    # Plain field edit — no state transition, no journal row
    # ------------------------------------------------------------------ #

    _UNSET = object()

    def update_fields(
        self,
        *,
        priority: str | None = None,
        needed_by=_UNSET,
        notes: str | None = None,
        quantity_requested: Decimal | None = None,
        serial_number_tracking_required: bool | None = None,
        actor=None,
    ) -> PartDemand:
        """Patch the plain descriptive fields (edit page's fields card, §2.3).

        Distinct from every verb above: this never writes a PartDemandUpdate
        journal row and never touches an axis column. `needed_by` accepts an
        explicit ``None`` (clear the date), so it is distinguished from "not
        supplied" via the module-level sentinel.

        `quantity_requested` only ever *raises* through here — an increase
        routes to PartDemandQuantityManager.raise_requested_quantity, which
        carries D28's cap bookkeeping. A decrease has no verb in this build
        (there is no "lower the ask" business rule specified) and is silently
        ignored rather than guessed at; the form is expected to disable
        lowering below the already-purchased quantity.
        """
        demand = self.demand
        update_fields: list[str] = []
        if priority is not None and priority != demand.priority:
            demand.priority = priority
            update_fields.append("priority")
        if needed_by is not self._UNSET and needed_by != demand.needed_by:
            demand.needed_by = needed_by
            update_fields.append("needed_by")
        if notes is not None and notes != demand.notes:
            demand.notes = notes
            update_fields.append("notes")
        if (
            serial_number_tracking_required is not None
            and serial_number_tracking_required != demand.serial_number_tracking_required
        ):
            demand.serial_number_tracking_required = serial_number_tracking_required
            update_fields.append("serial_number_tracking_required")

        if quantity_requested is not None and quantity_requested > demand.quantity_requested:
            self.raise_requested_quantity(new_quantity=quantity_requested, actor=actor)

        if update_fields:
            demand.updated_by = actor
            update_fields += ["updated_by", "updated_at"]
            demand.save(update_fields=update_fields)
        return demand

    def substitute_part(self, *, new_part_id: int, actor=None, notes: str = "") -> PartDemand:
        """Swap what is being asked for — "we don't stock that, use this".

        Not a state transition and deliberately writes no journal row: this
        changes the SUBJECT of the request, not its position on any of the four
        axes. What it does change is graph-load-bearing, so
        PartDemandSubstitutionPolicy refuses everything except a demand nothing
        has happened to yet, alone in its own graph; see that guard for why.

        The graph is recalculated rather than left alone, because
        GraphSummaryManager caches the part on the summary row and would
        otherwise keep pointing at the part that is no longer being requested.
        """
        demand = self.demand
        verdict = PartDemandSubstitutionPolicy.decide(
            demand=demand, new_part_id=new_part_id
        )
        if not verdict.allowed:
            raise TransitionRefused([verdict.reason])

        previous_part_id = demand.part_id
        with transaction.atomic():
            demand.part_id = new_part_id
            demand.updated_by = actor
            demand.notes = self._append_substitution_note(
                demand.notes, previous_part_id=previous_part_id, notes=notes
            )
            demand.save(update_fields=["part", "notes", "updated_by", "updated_at"])
            if demand.graph_id is not None:
                GraphSummaryManager.recalculate(graph_id=demand.graph_id)
        self._demand = None
        return self.demand

    @staticmethod
    def _append_substitution_note(
        existing: str, *, previous_part_id: int, notes: str
    ) -> str:
        """The substitution leaves its trace in notes because it writes no
        journal row — without this the swap would be invisible to the person
        who raised the demand."""
        trace = f"Part substituted (was part #{previous_part_id})."
        if notes.strip():
            trace = f"{trace} {notes.strip()}"
        return f"{existing}\n{trace}".strip() if existing else trace

    # ------------------------------------------------------------------ #
    # Quantities and lifecycle
    # ------------------------------------------------------------------ #

    def refresh_purchased_qty(self, *, actor=None, commit: bool = True) -> Decimal:
        return PartDemandQuantityManager.refresh_purchased_qty(
            demand=self.demand, actor=actor, commit=commit
        )

    def raise_requested_quantity(
        self, *, new_quantity: Decimal, actor=None, commit: bool = True
    ) -> Decimal:
        return PartDemandQuantityManager.raise_requested_quantity(
            demand=self.demand, new_quantity=new_quantity, actor=actor, commit=commit
        )

    def delete(self, *, actor=None) -> DeletionVerdict:
        """Hard delete only while untouched; otherwise deactivate (D6).

        'Untouched' means zero allocations and no journal rows beyond the four
        initializers. Once anything has happened to a demand, deletion becomes
        deactivation, never a hard delete.
        """
        demand = self.demand
        verdict = PartDemandDeletionPolicy.decide(demand=demand)
        with transaction.atomic():
            if verdict.hard_delete:
                demand.delete()
                self._demand = None
            else:
                from django.utils import timezone

                demand.deleted_at = timezone.now()
                demand.updated_by = actor
                demand.save(
                    update_fields=["deleted_at", "updated_by", "updated_at"]
                )
        return verdict
