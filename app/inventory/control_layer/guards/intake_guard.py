"""Guard types: StateMachine, Validator, Policy for the intake domain.

`IntakeSessionStateMachine` — legal `IntakeSession.status` transitions.
`AllocationValidator` — serial => qty 1.000, composite_sn uniqueness.
`AutoIntakeValidator` — the Auto Intake portal's monotonic floor/cap math
(`auto_intake_workflow_guide.md` §3).
`IntakePolicy` — the two-tier authorization surface: `can_intake_stock`
permission (checked at the presentation layer, mirroring `StockPolicy`'s
convention) plus the operator's data-domain coverage of the target
`Shipment` (checked inside `IntakeContext.associate_shipment`, since that is
where a session first touches a shipment's domain).
"""

from __future__ import annotations

from decimal import Decimal

from app.administration.models.data_ownership.user_assignments.user_domains import (
    UserDomain,
)
from app.inventory.control_layer.errors import (
    IntakeShipmentDomainAccessDenied,
    InventoryValidationError,
)
from app.inventory.models.intake.enums import IntakeSessionStatus
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.inventory.models.stock.active_inventory import ActiveInventory

INTAKE_SESSION_TRANSITIONS: dict[str, frozenset[str]] = {
    IntakeSessionStatus.DRAFT: frozenset(
        {IntakeSessionStatus.ACTIVE, IntakeSessionStatus.CANCELLED}
    ),
    # ACTIVE -> CLOSED directly is legal (FD-13): the Auto Intake path never
    # touches reconciliation because partial receipts are resolved by
    # splitting the shipment line, not by a reconciliation task.
    IntakeSessionStatus.ACTIVE: frozenset(
        {
            IntakeSessionStatus.RECONCILING,
            IntakeSessionStatus.CLOSED,
            IntakeSessionStatus.CANCELLED,
        }
    ),
    IntakeSessionStatus.RECONCILING: frozenset(
        {IntakeSessionStatus.CLOSED, IntakeSessionStatus.CANCELLED}
    ),
    IntakeSessionStatus.CLOSED: frozenset(),
    IntakeSessionStatus.CANCELLED: frozenset(),
}


class IntakeSessionStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> None:
        if from_status == to_status:
            raise InventoryValidationError(
                [f"The session is already '{from_status}'."]
            )
        legal = INTAKE_SESSION_TRANSITIONS.get(from_status, frozenset())
        if to_status not in legal:
            raise InventoryValidationError(
                [f"An intake session cannot move from '{from_status}' to '{to_status}'."]
            )


class AllocationValidator:
    @classmethod
    def check_quantity_positive(cls, *, quantity: Decimal) -> None:
        if quantity is None or quantity <= 0:
            raise InventoryValidationError(
                ["Allocation quantity must be greater than zero."]
            )

    @classmethod
    def check_serial_implies_unit_qty(cls, *, serial_number: str, quantity: Decimal) -> None:
        if serial_number and quantity != 1:
            raise InventoryValidationError(
                ["A serialized allocation's quantity must be exactly 1.000."]
            )

    @classmethod
    def check_composite_sn_unique(
        cls, *, part_id: int, serial_number: str, exclude_allocation_id: int | None = None
    ) -> None:
        """Serial uniqueness against every other live allocation AND live
        `ActiveInventory` — a serial already on the floor, or already staged
        in another allocation, cannot be logged again."""
        if not serial_number:
            return
        composite_sn = f"{part_id}:{serial_number}"

        alloc_qs = ItemAllocation.objects.filter(
            composite_sn=composite_sn, deleted_at__isnull=True
        )
        if exclude_allocation_id is not None:
            alloc_qs = alloc_qs.exclude(pk=exclude_allocation_id)
        if alloc_qs.exists():
            raise InventoryValidationError(
                [f"Serial '{serial_number}' is already logged on another live allocation."]
            )

        if ActiveInventory.objects.filter(
            part_id=part_id, serial_number=serial_number, quantity_on_hand__gt=0
        ).exists():
            raise InventoryValidationError(
                [f"Serial '{serial_number}' is already in stock for this part."]
            )


class AutoIntakeValidator:
    """The floor/cap math from `auto_intake_workflow_guide.md` §3.2 — the
    only three constraints, checked per shipment line before any delta is
    computed."""

    @classmethod
    def check_floor(
        cls, *, label: str, user_value: Decimal, existing_value: Decimal
    ) -> None:
        if user_value < existing_value:
            raise InventoryValidationError(
                [
                    f"Cannot reduce {label} quantity below existing allocation of "
                    f"{existing_value}."
                ]
            )

    @classmethod
    def check_cap(cls, *, accepted: Decimal, rejected: Decimal, shipped_qty: Decimal) -> None:
        total = accepted + rejected
        if total > shipped_qty:
            raise InventoryValidationError(
                [
                    f"Target accepted + rejected ({total}) cannot exceed the shipped "
                    f"quantity ({shipped_qty})."
                ]
            )

    @classmethod
    def check_line_targets(
        cls,
        *,
        accepted_user: Decimal,
        rejected_user: Decimal,
        accepted_existing: Decimal,
        rejected_existing: Decimal,
        shipped_qty: Decimal,
    ) -> None:
        cls.check_floor(
            label="accepted", user_value=accepted_user, existing_value=accepted_existing
        )
        cls.check_floor(
            label="rejected", user_value=rejected_user, existing_value=rejected_existing
        )
        cls.check_cap(accepted=accepted_user, rejected=rejected_user, shipped_qty=shipped_qty)


class IntakePolicy:
    """The two-tier authorization surface (mirrors `StockPolicy`): a Django
    permission, checked by whichever presentation-layer entrypoint owns the
    portal, plus data-domain coverage of the shipment being received against
    — enforced here since `IntakeContext.associate_shipment` is where a
    session first touches a shipment's domain."""

    @classmethod
    def check_permission(cls, *, actor, permission_codename: str = "inventory.can_intake_stock") -> None:
        if actor is None:
            return
        if not actor.has_perm(permission_codename):
            raise InventoryValidationError(
                [f"You do not have the '{permission_codename}' permission."]
            )

    @classmethod
    def check_shipment_domain_access(cls, *, actor, shipment) -> None:
        if actor is None:
            return
        if UserDomain.objects.filter(
            user=actor, domain_id=shipment.domain_id, is_active=True
        ).exists():
            return
        raise IntakeShipmentDomainAccessDenied(shipment_id=shipment.pk)
