"""Context: the entry point for control logic around one purchase_order_id."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.factories.part_price_observation_bulk_factory import (
    PartPriceObservationBulkFactory,
    PriceObservationInput,
)
from app.procurement.control_layer.guards.purchase_order_approval_guard import (
    PurchaseOrderApprovalStateMachine,
)
from app.procurement.control_layer.guards.purchase_order_state_guard import (
    PurchaseOrderStateMachine,
)
from app.procurement.control_layer.handlers.purchase_order_propagation_handler import (
    PropagationReport,
    PurchaseOrderPropagationHandler,
)
from app.procurement.control_layer.managers.purchase_order_cost_manager import (
    PurchaseOrderCostManager,
)
from app.procurement.control_layer.managers.purchase_order_demand_link_manager import (
    PurchaseOrderDemandLinkManager,
)
from app.procurement.control_layer.managers.purchase_order_line_manager import (
    PurchaseOrderLineManager,
)
from app.procurement.control_layer.narrators.purchase_order_narrator import (
    PurchaseOrderNarrator,
)
from app.procurement.models import (
    PartDemand,
    PriceConfidence,
    PriceSourceType,
    PurchaseOrder,
    PurchaseOrderApprovalState,
    PurchaseOrderStatus,
)
from app.procurement.presentation_layer.tools.po_events import (
    PurchaseOrderEventEmitter,
    PurchaseOrderEventPayload,
    PurchaseOrderEventType,
)


class PurchaseOrderContext:
    def __init__(self, purchase_order_id: int) -> None:
        self.purchase_order_id = purchase_order_id
        self._purchase_order: PurchaseOrder | None = None

    @classmethod
    def from_struct(cls, struct) -> "PurchaseOrderContext":
        return cls(struct.purchase_order_id)

    @property
    def purchase_order(self) -> PurchaseOrder:
        if self._purchase_order is None:
            self._purchase_order = PurchaseOrder.objects.select_related(
                "vendor", "domain", "event"
            ).get(pk=self.purchase_order_id)
        return self._purchase_order

    # ------------------------------------------------------------------ #
    # Status movement
    # ------------------------------------------------------------------ #

    def place(self, *, actor=None) -> PropagationReport:
        """Send the order to the vendor. THE MONEY-MOVED BOUNDARY.

        A PO must have at least one line to be placed — carried forward from
        the legacy submit_order, which got this right. D71: also blocked
        unless the approval axis has reached Approved — placing is the
        Buyer's act, approval is the purchasing manager's, and D2's old
        allowance for an Approver alone to place is retired.
        """
        po = self.purchase_order
        if not po.lines.filter(deleted_at__isnull=True).exists():
            raise ProcurementValidationError(
                ["A purchase order needs at least one line before it can be placed."]
            )
        if po.approval_state != PurchaseOrderApprovalState.APPROVED:
            raise ProcurementValidationError(
                ["This order must be approved before it can be placed."]
            )

        with transaction.atomic():
            self._move_status(to_status=PurchaseOrderStatus.PLACED, actor=actor)
            report = PurchaseOrderPropagationHandler.on_placed(
                purchase_order=po, actor=actor
            )
            self._write_ordered_observations(po=po, actor=actor)
            PurchaseOrderNarrator.post(
                purchase_order=po,
                message=PurchaseOrderNarrator.placed(po_number=po.po_number),
                actor=actor,
            )
            self._emit_status_change(
                actor=actor,
                previous_status=PurchaseOrderStatus.DRAFT,
                affected_demand_ids=report.affected_demand_ids,
            )
        return report

    @staticmethod
    def _write_ordered_observations(*, po: PurchaseOrder, actor) -> None:
        """Phase 7 (build_plan.md §8): placing a PO is itself a price fact —
        one `ordered` observation per line, self-maintaining because it exists
        only as a byproduct of work already being done (README.md "Out of
        scope" — no hand-maintained catalog).

        observed_at is the order date, never today (D85's "never today" rule
        applies here too). Confidence is copied from the line's own band;
        blank (not stated) becomes UNKNOWN rather than failing the guard,
        which requires a real PriceConfidence value with no default.
        """
        lines = list(po.lines.filter(deleted_at__isnull=True))
        rows = [
            PriceObservationInput(
                part_id=line.part_id,
                vendor_id=po.vendor_id,
                domain_id=po.domain_id,
                unit_cost=line.unit_cost,
                quantity=line.quantity_ordered,
                observed_at=po.order_date,
                source_type=PriceSourceType.ORDERED,
                confidence=line.unit_cost_confidence or PriceConfidence.UNKNOWN,
                source_po_line_id=line.pk,
            )
            for line in lines
        ]
        if not rows:
            return
        PartPriceObservationBulkFactory.create_many(
            rows=rows,
            actor=actor,
            visible_part_ids={line.part_id for line in lines},
            visible_domain_ids=[po.domain_id],
            actor_can_establish=False,
        )

    def mark_partially_received(self, *, actor=None) -> None:
        """Computed, not chosen: it follows from any accepted package quantity
        existing against this PO at all. Only the terminal close-out is human."""
        po = self.purchase_order
        if po.status != PurchaseOrderStatus.PLACED:
            return
        with transaction.atomic():
            previous = po.status
            self._move_status(
                to_status=PurchaseOrderStatus.PARTIALLY_RECEIVED, actor=actor
            )
            self._emit_status_change(actor=actor, previous_status=previous)

    def mark_received(self, *, actor=None) -> PropagationReport:
        """Declare receiving effectively complete, WHATEVER THE QUANTITIES SAY.

        Received is never reached by computing sum(quantity_accepted) >=
        sum(quantity_ordered). A Buyer can close out an order that received 6
        of a purchased 10, because that is what happened and the remaining 4
        are not coming — the vendor discontinued the item, the short shipment
        was accepted, the backorder was written off.
        """
        po = self.purchase_order
        with transaction.atomic():
            previous = po.status
            self._move_status(to_status=PurchaseOrderStatus.RECEIVED, actor=actor)
            report = PurchaseOrderPropagationHandler.on_received(
                purchase_order=po, actor=actor
            )
            PurchaseOrderNarrator.post(
                purchase_order=po,
                message=PurchaseOrderNarrator.received(po_number=po.po_number),
                actor=actor,
            )
            self._emit_status_change(
                actor=actor,
                previous_status=previous,
                affected_demand_ids=report.affected_demand_ids,
            )
        return report

    def cancel(self, *, actor=None, reason: str = "") -> PropagationReport:
        """Call off the order and free what it had claimed.

        ORDER MATTERS HERE: demands are propagated to Cancelled BEFORE their
        allocations are released, because releasing sets is_active=False and
        the propagation query only walks active allocations. Releasing first
        would silently propagate to nobody.
        """
        po = self.purchase_order
        with transaction.atomic():
            previous = po.status
            self._move_status(to_status=PurchaseOrderStatus.CANCELLED, actor=actor)

            report = PurchaseOrderPropagationHandler.on_cancelled(
                purchase_order=po, actor=actor
            )
            released = PurchaseOrderDemandLinkManager.release_for_purchase_order(
                purchase_order=po, actor=actor, commit=True
            )

            PurchaseOrderNarrator.post(
                purchase_order=po,
                message=PurchaseOrderNarrator.cancelled(
                    po_number=po.po_number, reason=reason
                ),
                actor=actor,
            )
            if released:
                PurchaseOrderNarrator.post(
                    purchase_order=po,
                    message=PurchaseOrderNarrator.allocations_released(count=released),
                    actor=actor,
                )
            self._emit_status_change(
                actor=actor,
                previous_status=previous,
                affected_demand_ids=report.affected_demand_ids,
            )
        return report

    # ------------------------------------------------------------------ #
    # Approval axis (D71/D76) — separate from status movement above
    # ------------------------------------------------------------------ #

    def submit_for_approval(self, *, actor=None) -> None:
        """Always available, never automatic — no cost thresholds in this
        build (deferred to the process-template engine)."""
        self._move_approval_state(
            to_state=PurchaseOrderApprovalState.PENDING_APPROVAL, actor=actor
        )
        po = self.purchase_order
        PurchaseOrderNarrator.post(
            purchase_order=po,
            message=PurchaseOrderNarrator.submitted_for_approval(
                po_number=po.po_number
            ),
            actor=actor,
        )

    def approve_order(self, *, actor=None) -> None:
        """Self-approval is legal — one person may hold both `buy` and
        `purchase_approve` and approve their own order. Never blocked,
        always recorded (see PurchaseOrderNarrator.approved)."""
        po = self.purchase_order
        self._move_approval_state(
            to_state=PurchaseOrderApprovalState.APPROVED, actor=actor
        )
        self_approved = actor is not None and actor.pk == po.created_by_id
        PurchaseOrderNarrator.post(
            purchase_order=po,
            message=PurchaseOrderNarrator.approved(
                po_number=po.po_number, self_approved=self_approved
            ),
            actor=actor,
        )

    def deny_order(self, *, actor=None) -> None:
        po = self.purchase_order
        self._move_approval_state(
            to_state=PurchaseOrderApprovalState.DENIED, actor=actor
        )
        PurchaseOrderNarrator.post(
            purchase_order=po,
            message=PurchaseOrderNarrator.denied(po_number=po.po_number),
            actor=actor,
        )

    def _move_approval_state(self, *, to_state: str, actor=None) -> None:
        po = self.purchase_order
        verdict = PurchaseOrderApprovalStateMachine.check(
            from_state=po.approval_state, to_state=to_state
        )
        if not verdict.allowed:
            raise ProcurementValidationError([verdict.reason])
        po.approval_state = to_state
        po.updated_by = actor
        po.save(update_fields=["approval_state", "updated_by", "updated_at"])

    # ------------------------------------------------------------------ #
    # Lines and allocations
    # ------------------------------------------------------------------ #

    def add_line(
        self,
        *,
        part_id: int,
        quantity_ordered: Decimal,
        unit_cost: Decimal,
        expected_delivery_date=None,
        notes: str = "",
        unit_cost_source: str = "",
        unit_cost_confidence: str = "",
        unit_cost_asserted_at=None,
        actor=None,
    ):
        with transaction.atomic():
            return PurchaseOrderLineManager.add_line(
                purchase_order=self.purchase_order,
                part_id=part_id,
                quantity_ordered=quantity_ordered,
                unit_cost=unit_cost,
                expected_delivery_date=expected_delivery_date,
                notes=notes,
                unit_cost_source=unit_cost_source,
                unit_cost_confidence=unit_cost_confidence,
                unit_cost_asserted_at=unit_cost_asserted_at,
                actor=actor,
            )

    def edit_line(self, *, line, changes: dict, actor=None):
        with transaction.atomic():
            return PurchaseOrderLineManager.edit_line(
                line=line, changes=changes, actor=actor
            )

    def cancel_line(self, *, line, actor=None) -> int:
        with transaction.atomic():
            return PurchaseOrderLineManager.cancel_line(line=line, actor=actor)

    def allocate(
        self,
        *,
        line,
        demand: PartDemand,
        quantity_allocated: Decimal,
        actor=None,
        auto_approve: bool = True,
        allow_raise_request: bool = False,
        notes: str = "",
    ):
        with transaction.atomic():
            return PurchaseOrderDemandLinkManager.allocate(
                line=line,
                demand=demand,
                quantity_allocated=quantity_allocated,
                actor=actor,
                auto_approve=auto_approve,
                allow_raise_request=allow_raise_request,
                notes=notes,
            )

    def delink(self, *, link, actor=None) -> None:
        with transaction.atomic():
            PurchaseOrderDemandLinkManager.delink(link=link, actor=actor)

    def recompute_cost(self, *, actor=None) -> Decimal:
        return PurchaseOrderCostManager.recompute(
            purchase_order=self.purchase_order, actor=actor
        )

    # ------------------------------------------------------------------ #

    def _move_status(self, *, to_status: str, actor=None) -> None:
        po = self.purchase_order
        verdict = PurchaseOrderStateMachine.check(
            from_status=po.status, to_status=to_status
        )
        if not verdict.allowed:
            raise ProcurementValidationError([verdict.reason])

        previous = po.status
        po.status = to_status
        po.updated_by = actor
        po.save(update_fields=["status", "updated_by", "updated_at"])

        PurchaseOrderNarrator.post(
            purchase_order=po,
            message=PurchaseOrderNarrator.status_changed(
                from_status=previous, to_status=to_status
            ),
            actor=actor,
        )

    def _emit_status_change(
        self,
        *,
        actor=None,
        previous_status: str,
        affected_demand_ids: tuple[int, ...] = (),
    ) -> None:
        po = self.purchase_order
        PurchaseOrderEventEmitter.emit(
            PurchaseOrderEventPayload(
                event_type=PurchaseOrderEventType.PO_STATUS_CHANGED,
                purchase_order_id=po.pk,
                po_number=po.po_number,
                status=po.status,
                previous_status=previous_status,
                occurred_at=timezone.now(),
                actor_id=getattr(actor, "pk", None),
                affected_demand_ids=affected_demand_ids,
            )
        )
