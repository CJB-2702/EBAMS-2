"""The only writer of PartDemand.purchased_qty and issued_qty.

purchased_qty is RECOMPUTED here from the allocation rows this app owns.
issued_qty is APPLIED here from a caller-supplied number — it cannot be
recomputed, because the rows behind it live in app/inventory/ and procurement
may not look. See PartDemandIssuanceManager for that seam.

NOTE ON ``commit``: throughout this app it means "do not open your own
transaction", NOT "do not write". Every method here writes its column either
way — the caller is expected to already hold an atomic block. Treating it as
"skip the write" is what silently left purchased_qty at 0 for every demand
created through the PO wizard, since the factory passes commit=False.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum


class PartDemandQuantityManager:
    @classmethod
    def refresh_purchased_qty(cls, *, demand, actor=None, commit: bool = True) -> Decimal:
        """Sum quantity_allocated across the demand's ACTIVE, non-deleted
        allocations. Released (is_active=False) and de-linked (soft-deleted)
        rows are both excluded, which is what frees a Buyer to re-allocate
        after a PO is cancelled."""
        total = demand.allocations.filter(
            is_active=True, deleted_at__isnull=True
        ).aggregate(total=Sum("quantity_allocated"))["total"] or Decimal("0")

        demand.purchased_qty = total
        demand.updated_by = actor
        demand.save(update_fields=["purchased_qty", "updated_by", "updated_at"])
        return total

    @classmethod
    def apply_issued_qty(
        cls, *, demand, net_issued_qty: Decimal, actor=None, commit: bool = True
    ) -> Decimal:
        """Set issued_qty to the caller-supplied NET quantity.

        No cap in either direction (D30): issued_qty may exceed or fall short
        of both purchased_qty and quantity_requested with no validation
        blocking it. A work order might call for 5 gallons of oil and need 4.5.
        This app records what happened; it does not dictate what should have.

        It may legitimately be 0 — a demand that issued 10 and had all 10
        returned nets to 0, which is a valid resting value, not an error (D39).
        """
        demand.issued_qty = net_issued_qty
        demand.updated_by = actor
        demand.save(update_fields=["issued_qty", "updated_by", "updated_at"])
        return net_issued_qty

    @classmethod
    def raise_requested_quantity(
        cls, *, demand, new_quantity: Decimal, actor=None, commit: bool = True
    ) -> Decimal:
        """D28's explicit-choice path: the Buyer raises the request to cover an
        allocation that exceeded it.

        Only ever called after a caller has resolved AllocationCapExceeded by
        explicitly choosing to raise. Raising the request to make a bulk buy
        fit is falsifying what somebody asked for, so the UI carries a strong
        warning; this method is the mechanical half.
        """
        demand.quantity_requested = new_quantity
        demand.updated_by = actor
        demand.save(update_fields=["quantity_requested", "updated_by", "updated_at"])
        return new_quantity
