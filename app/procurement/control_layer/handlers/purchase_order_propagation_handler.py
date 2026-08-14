"""Handler: D40's PurchaseOrder.status -> demand-axes propagation.

  PO status              purchasing_state      shipment_state
  ---------------------  --------------------  ---------------------------
  Draft                  stays unset           Request Not Sent
  Placed                 -> Purchased          -> Request Received by Vendor
  Partially Received     unchanged             unchanged (packages drive it)
  Received               unchanged             -> Delivered to Local (explicit)
  Cancelled              -> Cancelled          unchanged

Every write goes through PartDemandStateManager.transition() with
is_system_generated=True and actor set to whoever moved the PO. This handler
never assigns a snapshot column directly.

A demand linked to more than one PO takes the propagation from whichever PO
moved. Purchased means money moved for this demand somewhere — it is not a
per-PO fact.

REFUSALS DO NOT FAIL THE WORKFLOW. Gate 1 is checked during propagation, so a
demand still unapproved (the Buyer opted out of D42's auto-approve) will not
move, and the propagation skips it without failing the placement. The PO is
placed; that demand's purchasing axis waits for its Approver. That is exactly
the case the opt-out exists to create.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import (
    DemandDimension,
    PartDemand,
    PurchasingState,
    ShipmentState,
)


@dataclass
class PropagationReport:
    """What moved and what did not. Skips are reported, never swallowed —
    a Buyer needs to know which demands stayed behind and why."""

    moved_demand_ids: list[int]
    skipped: list[tuple[int, str]]

    @property
    def affected_demand_ids(self) -> tuple[int, ...]:
        return tuple(self.moved_demand_ids)


class PurchaseOrderPropagationHandler:
    @classmethod
    def linked_demands(cls, *, purchase_order) -> list[PartDemand]:
        """Every demand with an active allocation on a live line of this PO."""
        return list(
            PartDemand.objects.filter(
                allocations__purchase_order_line__purchase_order=purchase_order,
                allocations__is_active=True,
                allocations__deleted_at__isnull=True,
                allocations__purchase_order_line__deleted_at__isnull=True,
                deleted_at__isnull=True,
            ).distinct()
        )

    @classmethod
    def on_placed(cls, *, purchase_order, actor=None) -> PropagationReport:
        report = PropagationReport(moved_demand_ids=[], skipped=[])
        note = PartDemandNarrator.propagated_from_purchase_order(
            po_number=purchase_order.po_number
        )

        for demand in cls.linked_demands(purchase_order=purchase_order):
            # The money-moved boundary. Gate 1 is checked here.
            result = PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.PURCHASING,
                to_stage=PurchasingState.PURCHASED,
                actor=actor,
                notes=note,
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            if result.moved:
                report.moved_demand_ids.append(demand.pk)
            else:
                report.skipped.append((demand.pk, result.refusal))

            # An optimistic default. The middle stretch of the chain
            # (Production in Progress -> Vendor Prepared to Ship -> Shipped) is
            # advanced manually as vendor updates arrive; nothing computes it.
            PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.SHIPMENT,
                to_stage=ShipmentState.REQUEST_RECEIVED_BY_VENDOR,
                actor=actor,
                notes=note,
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
        return report

    @classmethod
    def on_received(cls, *, purchase_order, actor=None) -> PropagationReport:
        """The Buyer's explicit close-out. NEVER a quantity match (D29, D40) —
        an order that received 6 of a purchased 10 can be closed out, because
        that is what happened and the remaining 4 are not coming."""
        report = PropagationReport(moved_demand_ids=[], skipped=[])
        note = PartDemandNarrator.propagated_from_purchase_order(
            po_number=purchase_order.po_number
        )

        for demand in cls.linked_demands(purchase_order=purchase_order):
            result = PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.SHIPMENT,
                to_stage=ShipmentState.DELIVERED_TO_LOCAL,
                actor=actor,
                notes=note,
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            if result.moved:
                report.moved_demand_ids.append(demand.pk)
            else:
                report.skipped.append((demand.pk, result.refusal))
        return report

    @classmethod
    def on_cancelled(cls, *, purchase_order, actor=None) -> PropagationReport:
        """purchasing_state -> Cancelled. shipment_state is left alone: what
        arrived, arrived."""
        report = PropagationReport(moved_demand_ids=[], skipped=[])
        note = PartDemandNarrator.released_by_po_cancellation(
            po_number=purchase_order.po_number
        )

        for demand in cls.linked_demands(purchase_order=purchase_order):
            result = PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.PURCHASING,
                to_stage=PurchasingState.CANCELLED,
                actor=actor,
                notes=note,
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            if result.moved:
                report.moved_demand_ids.append(demand.pk)
            else:
                report.skipped.append((demand.pk, result.refusal))
        return report
