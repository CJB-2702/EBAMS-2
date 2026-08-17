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

from django.db.models import Sum

from app.procurement.control_layer.domain_structs.arrival_allocation import (
    accepted_by_purchase_order_line,
)
from app.procurement.control_layer.errors import (
    AllocationCapExceeded,
    CrossOrderAllocationExceeded,
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

        # §10's hard stop, checked BEFORE the same-line cap: a demand's total
        # across every order it touches must never exceed what it needs,
        # regardless of whether any single line's own cap would allow it.
        cls._check_cross_order_cap(demand=demand, line=line, quantity_allocated=quantity_allocated)

        cls._check_cap(
            demand=demand,
            quantity_allocated=quantity_allocated,
            existing_link=existing_link,
            allow_raise_request=allow_raise_request,
        )

    @classmethod
    def _check_cross_order_cap(cls, *, demand, line, quantity_allocated: Decimal) -> None:
        """reallocation_resolution_portal.md §10, rule 1: hard stop, always —
        deliberately no `allow_raise_request` escape hatch here, unlike the
        same-line cap this sits beside. Always computed fresh from the DB
        (rule 3) — nothing here reads a cached total.
        """
        other_claims = list(
            PurchaseOrderDemandLink.objects.filter(
                part_demand=demand, is_active=True, deleted_at__isnull=True
            )
            .exclude(purchase_order_line=line)
            .select_related("purchase_order_line__purchase_order")
            .order_by("-quantity_allocated")
        )
        if not other_claims:
            # Everything this demand claims lives on this one line — the
            # same-line cap in _check_cap already governs that case.
            return

        other_total = sum((c.quantity_allocated for c in other_claims), Decimal("0"))
        new_total = other_total + quantity_allocated
        if new_total > demand.quantity_requested:
            conflicting = other_claims[0]
            raise CrossOrderAllocationExceeded(
                demand_id=demand.pk,
                quantity_requested=demand.quantity_requested,
                total_across_orders=new_total,
                attempted=quantity_allocated,
                conflicting_purchase_order_id=conflicting.purchase_order_line.purchase_order_id,
                conflicting_po_number=conflicting.purchase_order_line.purchase_order.po_number,
                conflicting_line_number=conflicting.purchase_order_line.line_number,
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

    @classmethod
    def check_receipt(
        cls, *, link: PurchaseOrderDemandLink, quantity_received: Decimal
    ) -> None:
        """Reallocation Resolution decision (supersedes D55 — see
        PurchaseOrderDemandLink's docstring): a claim's quantity_received is a
        deliberate, human-typed distribution of a PO line's arrived total,
        never inferred. Enforced here:

          - a receipt total only grows (mirrors ShipmentLineValidator's
            acceptance simplicity) — a Buyer correcting an over-count reverses
            it through the unlock sequence, not by typing a smaller number
            over a locked claim;
          - the sum of every active claim's quantity_received on this line can
            never exceed what the line has actually had accepted against it —
            you cannot mark more received than physically arrived.
        """
        errors: list[str] = []

        if quantity_received is None or quantity_received < 0:
            errors.append("Received quantity cannot be negative.")
        elif quantity_received < link.quantity_received:
            errors.append(
                "Received quantity cannot be reduced once recorded. Use the "
                "Reallocation Portal's unlock sequence to correct a claim "
                "that was locked in error."
            )

        if errors:
            raise ProcurementValidationError(errors)

        line = link.purchase_order_line
        accepted_total = accepted_by_purchase_order_line(
            purchase_order_line_ids=[line.pk]
        ).get(line.pk, Decimal("0"))
        other_total = (
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line=line, is_active=True, deleted_at__isnull=True
            )
            .exclude(pk=link.pk)
            .aggregate(total=Sum("quantity_received"))["total"]
            or Decimal("0")
        )
        if other_total + quantity_received > accepted_total:
            raise ProcurementValidationError(
                [
                    f"Only {accepted_total} has been accepted against this line "
                    f"({other_total} already marked received on its other claims); "
                    f"{quantity_received} would exceed that."
                ]
            )
