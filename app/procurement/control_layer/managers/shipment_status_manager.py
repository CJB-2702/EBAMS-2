"""Manager: shipment status advance, shipment_state propagation, and the
mixed_po_assignments drift flag.

  Shipment.status                           -> PartDemand.shipment_state
  ---------------------------------------  ----------------------------------
  Awaiting Shipment                        Vendor Prepared to Ship
  Shipped                                  Shipped
  Delivered to Depot                       Delivered to Depot
  Delivered to Local Receiving Location    Delivered to Local Receiving Location
  Lost                                     Lost
  Accepted                                 (no change — acceptance is
                                            inspection, not movement)

The demand path is shipment line -> PurchaseOrderShipmentLink ->
purchase_order_line -> PurchaseOrderDemandLink -> PartDemand, and every write
goes through
PartDemandStateManager.transition() with is_system_generated=True — never a
direct column assignment.

A DEMAND BEHIND SEVERAL SHIPMENTS TAKES THE LEAST ADVANCED STATUS AMONG THEM.
Backordered items ship in pieces, so a demand's line can have shipment lines in
several shipments at different statuses. A demand with one box delivered and one
still in transit has NOT been delivered; taking the most advanced would report
the demand as complete while material is still moving.
"""

from __future__ import annotations

from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.models import (
    DemandDimension,
    ShipmentStatus,
    PartDemand,
    PurchaseOrderShipmentLink,
    ShipmentState,
)

#: Shipment status -> the shipment_state it drives. ACCEPTED is deliberately
#: absent: it records that goods arrived intact, not that they moved.
SHIPMENT_STATUS_TO_SHIPMENT_STATE: dict[str, str] = {
    ShipmentStatus.AWAITING_SHIPMENT: ShipmentState.VENDOR_PREPARED_TO_SHIP,
    ShipmentStatus.SHIPPED: ShipmentState.SHIPPED,
    ShipmentStatus.DELIVERED_TO_DEPOT: ShipmentState.DELIVERED_TO_DEPOT,
    ShipmentStatus.DELIVERED_TO_LOCAL: ShipmentState.DELIVERED_TO_LOCAL,
    ShipmentStatus.LOST: ShipmentState.LOST,
}

#: How advanced each shipment status is, for the least-advanced rule. Lost sorts
#: lowest because a lost box is the least progress there is.
_SHIPMENT_STATUS_RANK: dict[str, int] = {
    ShipmentStatus.LOST: 0,
    ShipmentStatus.AWAITING_SHIPMENT: 1,
    ShipmentStatus.SHIPPED: 2,
    ShipmentStatus.DELIVERED_TO_DEPOT: 3,
    ShipmentStatus.DELIVERED_TO_LOCAL: 4,
    ShipmentStatus.ACCEPTED: 5,
}


class ShipmentStatusManager:
    @classmethod
    def refresh_mixed_po_assignments(cls, *, shipment, actor=None, commit: bool = True) -> bool:
        """Set the drift flag if any allocation points at a line on a
        different PO.

        Blocks nothing. It exists so the condition is queryable rather than
        puzzled over.
        """
        drifted = (
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line__shipment=shipment,
                shipment_line__deleted_at__isnull=True,
                deleted_at__isnull=True,
            )
            .exclude(
                purchase_order_line__purchase_order_id=shipment.purchase_order_id
            )
            .exists()
        )
        if drifted != shipment.mixed_po_assignments:
            shipment.mixed_po_assignments = drifted
            shipment.updated_by = actor
            if commit:
                shipment.save(
                    update_fields=[
                        "mixed_po_assignments",
                        "updated_by",
                        "updated_at",
                    ]
                )
        return drifted

    @classmethod
    def propagate_shipment_state(cls, *, shipment, actor=None) -> list[int]:
        """Move shipment_state on every demand behind this shipment's lines.

        Each demand is evaluated against ALL shipments touching its line, and
        takes the least advanced — see the module docstring.
        """
        demands = PartDemand.objects.filter(
            allocations__is_active=True,
            allocations__deleted_at__isnull=True,
            allocations__purchase_order_line__shipment_links__shipment_line__shipment=shipment,
            allocations__purchase_order_line__shipment_links__deleted_at__isnull=True,
            allocations__purchase_order_line__shipment_links__shipment_line__deleted_at__isnull=True,
            deleted_at__isnull=True,
        ).distinct()

        moved: list[int] = []
        for demand in demands:
            effective_status = cls._least_advanced_status_for_demand(demand=demand)
            to_stage = SHIPMENT_STATUS_TO_SHIPMENT_STATE.get(effective_status)
            if to_stage is None:
                continue
            result = PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.SHIPMENT,
                to_stage=to_stage,
                actor=actor,
                notes=PartDemandNarrator.propagated_from_shipment(
                    shipment_number=shipment.shipment_number
                ),
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            if result.moved:
                moved.append(demand.pk)
        return moved

    @staticmethod
    def _least_advanced_status_for_demand(*, demand) -> str:
        """The least advanced status among every shipment carrying material for
        this demand."""
        statuses = (
            demand.allocations.filter(
                is_active=True,
                deleted_at__isnull=True,
                purchase_order_line__shipment_links__deleted_at__isnull=True,
                purchase_order_line__shipment_links__shipment_line__deleted_at__isnull=True,
            )
            .values_list(
                "purchase_order_line__shipment_links__shipment_line__shipment__status",
                flat=True,
            )
            .distinct()
        )
        known = [s for s in statuses if s in _SHIPMENT_STATUS_RANK]
        if not known:
            return ""
        return min(known, key=lambda s: _SHIPMENT_STATUS_RANK[s])
