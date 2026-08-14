"""Guard type: Validator. D28's cap decision, the part-match check, and
duplicate pairing.

THE CAP IS PER DEMAND, NEVER PER LINE. A demand's outstanding need is
quantity_requested - purchased_qty, and the allocation write path enforces that
as a real cap. But a PurchaseOrderLine is always free to carry more ordered
quantity than the sum of its allocations — that is three legitimate cases at
once (D14, D28): proactive/bulk restocking, a vendor minimum order quantity,
and reserve for a demand that does not exist yet.

The legacy PurchaseOrderLinkManager.link_demand had this backwards: it checked
demand_quantity > (quantity_ordered - already_allocated) and refused, capping
against the LINE's remaining quantity and silently allocating the demand's full
quantity with no partial option. That made splitting one demand across two POs
impossible — the exact case the many-to-many join exists for.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.errors import (
    AllocationCapExceeded,
    ProcurementValidationError,
)
from app.procurement.models import PurchaseOrderDemandLink


class PurchaseOrderDemandLinkValidator:
    @classmethod
    def check(
        cls,
        *,
        demand,
        line,
        quantity_allocated: Decimal,
        existing_link: PurchaseOrderDemandLink | None = None,
        allow_raise_request: bool = False,
    ) -> None:
        """Raises on refusal. AllocationCapExceeded is the special case: it is
        NOT a flat failure but a choice the caller must resolve (raise the
        request, or leave the excess unallocated)."""
        errors: list[str] = []

        if quantity_allocated is None or quantity_allocated <= 0:
            errors.append("Allocated quantity must be greater than zero.")

        # Carried forward from the legacy add_link_to_line, which got this
        # right: allocating a demand for one part to a line buying a different
        # part is never intentional. Enforced here rather than as a DB
        # constraint because it spans three tables.
        if demand.part_id != line.part_id:
            errors.append(
                f"Demand #{demand.pk} is for a different part than line "
                f"#{line.pk}. Allocations must match on part."
            )

        # One allocation per pairing. A Buyer who wants more edits the existing
        # row; they never create a second.
        if existing_link is None:
            duplicate = PurchaseOrderDemandLink.objects.filter(
                part_demand=demand,
                purchase_order_line=line,
                deleted_at__isnull=True,
            ).exists()
            if duplicate:
                errors.append(
                    "This demand is already allocated to this line. Edit the "
                    "existing allocation instead of adding a second."
                )

        if errors:
            raise ProcurementValidationError(errors)

        cls._check_cap(
            demand=demand,
            quantity_allocated=quantity_allocated,
            existing_link=existing_link,
            allow_raise_request=allow_raise_request,
        )

    @staticmethod
    def _check_cap(
        *,
        demand,
        quantity_allocated: Decimal,
        existing_link: PurchaseOrderDemandLink | None,
        allow_raise_request: bool,
    ) -> None:
        if allow_raise_request:
            # The caller has already resolved the choice by electing to raise
            # the request; the cap no longer applies to this write.
            return

        # An edit replaces its own row's contribution rather than adding to it.
        already = demand.purchased_qty
        if existing_link is not None and existing_link.is_active:
            already = already - existing_link.quantity_allocated

        outstanding = demand.quantity_requested - already
        if outstanding <= 0:
            raise AllocationCapExceeded(
                demand_id=demand.pk,
                quantity_requested=demand.quantity_requested,
                purchased_qty=already,
                outstanding=Decimal("0"),
                attempted=quantity_allocated,
            )

        # Binary allocation: quantity must equal the full outstanding amount.
        # No partial allocation allowed — either the full amount is allocated
        # or nothing is (user must purchase more later if not enough).
        if quantity_allocated != outstanding:
            raise AllocationCapExceeded(
                demand_id=demand.pk,
                quantity_requested=demand.quantity_requested,
                purchased_qty=already,
                outstanding=outstanding,
                attempted=quantity_allocated,
                binary_allocation=True,
            )
