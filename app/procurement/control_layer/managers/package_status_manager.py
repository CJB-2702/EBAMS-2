"""Manager: package status advance, shipment_state propagation, and the
mixed_po_assignments drift flag.

  Package.status                           -> PartDemand.shipment_state
  ---------------------------------------  ----------------------------------
  Awaiting Shipment                        Vendor Prepared to Ship
  Shipped                                  Shipped
  Delivered to Depot                       Delivered to Depot
  Delivered to Local Receiving Location    Delivered to Local Receiving Location
  Lost                                     Lost
  Accepted                                 (no change — acceptance is
                                            inspection, not movement)

The demand path is package line -> purchase_order_line ->
PurchaseOrderDemandLink -> PartDemand, and every write goes through
PartDemandStateManager.transition() with is_system_generated=True — never a
direct column assignment.

A DEMAND BEHIND SEVERAL PACKAGES TAKES THE LEAST ADVANCED STATUS AMONG THEM.
Backordered items ship in pieces, so a demand's line can have package lines in
several packages at different statuses. A demand with one box delivered and one
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
    PackageStatus,
    PartDemand,
    ShipmentState,
)

#: Package status -> the shipment_state it drives. ACCEPTED is deliberately
#: absent: it records that goods arrived intact, not that they moved.
PACKAGE_STATUS_TO_SHIPMENT_STATE: dict[str, str] = {
    PackageStatus.AWAITING_SHIPMENT: ShipmentState.VENDOR_PREPARED_TO_SHIP,
    PackageStatus.SHIPPED: ShipmentState.SHIPPED,
    PackageStatus.DELIVERED_TO_DEPOT: ShipmentState.DELIVERED_TO_DEPOT,
    PackageStatus.DELIVERED_TO_LOCAL: ShipmentState.DELIVERED_TO_LOCAL,
    PackageStatus.LOST: ShipmentState.LOST,
}

#: How advanced each package status is, for the least-advanced rule. Lost sorts
#: lowest because a lost box is the least progress there is.
_PACKAGE_STATUS_RANK: dict[str, int] = {
    PackageStatus.LOST: 0,
    PackageStatus.AWAITING_SHIPMENT: 1,
    PackageStatus.SHIPPED: 2,
    PackageStatus.DELIVERED_TO_DEPOT: 3,
    PackageStatus.DELIVERED_TO_LOCAL: 4,
    PackageStatus.ACCEPTED: 5,
}


class PackageStatusManager:
    @classmethod
    def refresh_mixed_po_assignments(cls, *, package, actor=None, commit: bool = True) -> bool:
        """Set the drift flag if any line points at a line on a different PO.

        Blocks nothing. It exists so the condition is queryable rather than
        puzzled over.
        """
        drifted = (
            package.lines.filter(deleted_at__isnull=True)
            .exclude(purchase_order_line__isnull=True)
            .exclude(purchase_order_line__purchase_order_id=package.purchase_order_id)
            .exists()
        )
        if drifted != package.mixed_po_assignments:
            package.mixed_po_assignments = drifted
            package.updated_by = actor
            if commit:
                package.save(
                    update_fields=[
                        "mixed_po_assignments",
                        "updated_by",
                        "updated_at",
                    ]
                )
        return drifted

    @classmethod
    def propagate_shipment_state(cls, *, package, actor=None) -> list[int]:
        """Move shipment_state on every demand behind this package's lines.

        Each demand is evaluated against ALL packages touching its line, and
        takes the least advanced — see the module docstring.
        """
        demands = PartDemand.objects.filter(
            allocations__is_active=True,
            allocations__deleted_at__isnull=True,
            allocations__purchase_order_line__package_lines__package=package,
            allocations__purchase_order_line__package_lines__deleted_at__isnull=True,
            deleted_at__isnull=True,
        ).distinct()

        moved: list[int] = []
        for demand in demands:
            effective_status = cls._least_advanced_status_for_demand(demand=demand)
            to_stage = PACKAGE_STATUS_TO_SHIPMENT_STATE.get(effective_status)
            if to_stage is None:
                continue
            result = PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.SHIPMENT,
                to_stage=to_stage,
                actor=actor,
                notes=PartDemandNarrator.propagated_from_package(
                    package_number=package.package_number
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
        """The least advanced status among every package carrying material for
        this demand."""
        statuses = (
            demand.allocations.filter(
                is_active=True,
                deleted_at__isnull=True,
                purchase_order_line__package_lines__deleted_at__isnull=True,
            )
            .values_list(
                "purchase_order_line__package_lines__package__status", flat=True
            )
            .distinct()
        )
        known = [s for s in statuses if s in _PACKAGE_STATUS_RANK]
        if not known:
            return ""
        return min(known, key=lambda s: _PACKAGE_STATUS_RANK[s])
