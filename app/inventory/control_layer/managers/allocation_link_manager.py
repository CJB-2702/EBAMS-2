"""Manager: THE one place an ItemAllocation's shipment_line is ever set.

    for any ShipmentLine L:  sum(live allocations linked to L) <= L.quantity

This is the over-allocation ban (intake_portal_workflow.md §7.2, §12.6), and
it is the decision that lets the entire approval concept be deleted. The most
damaging discrepancy — a line claiming more received than was ever ordered —
simply cannot be created, so nobody needs to review it after the fact.

WHY IT IS NOT A DATABASE CONSTRAINT. It is an aggregate ACROSS ROWS. A
`CheckConstraint` sees one row at a time and cannot sum siblings, so the rule
has to live here, with the line LOCKED FOR UPDATE while the sum is checked and
the write applied. Without that lock two concurrent links each read 45/50, each
decide 5 more fits, and the line lands at 55.

WHY EVERY PATH COMES THROUGH HERE. Auto-association (§5.2), manual linking on
the associate page (§7.3), and the global allocation portal are three UIs over
one rule. A second linking path would be a second place for the ban to be
forgotten, and the ban is load-bearing for a design that has no other defence.

ENFORCED AT WRITE TIME, NOT AS A STANDING INVARIANT. If procurement later
reduces a line's quantity below what is already allocated, the existing rows
stand. That is a report on the discrepancy page, not a violation to repair
(§7.2).

FULL IS NOT AN ERROR. When a line cannot take more, the caller gets an
explanation — "this line is fully allocated (50/50), the rest stays unlinked
as excess" — because unlinked is a terminal, ordinary state, not a failure.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from app.inventory.control_layer.domain_structs.shipment_line_truth_struct import (
    ZERO,
    live_allocations_for_line,
)
from app.inventory.control_layer.errors import LineCapacityExceeded
from app.inventory.models.intake.enums import AllocationLinkSource
from app.inventory.models.intake.item_allocation import ItemAllocation


class AllocationLinkManager:
    # ------------------------------------------------------------------ #
    # Capacity
    # ------------------------------------------------------------------ #

    @classmethod
    def remaining_capacity(cls, *, shipment_line_id: int, expected: Decimal | None = None,
                           exclude_allocation_id: int | None = None) -> Decimal:
        """How much more may be linked to this line, counting EVERY session's
        live rows (§5.5). Never negative.

        `exclude_allocation_id` lets a row that is already on the line ask
        "could I grow?" without counting itself twice.
        """
        from app.procurement.models import ShipmentLine

        if expected is None:
            expected = (
                ShipmentLine.objects.filter(pk=shipment_line_id)
                .values_list("quantity", flat=True)
                .first()
            ) or ZERO

        rows = live_allocations_for_line(shipment_line_id)
        if exclude_allocation_id is not None:
            rows = rows.exclude(pk=exclude_allocation_id)
        linked = rows.aggregate(t=Sum("quantity"))["t"] or ZERO
        return max(expected - linked, ZERO)

    @classmethod
    def _assert_capacity(
        cls, *, shipment_line_id: int, quantity: Decimal,
        exclude_allocation_id: int | None = None,
    ):
        """Lock the line, check the sum, and either return the locked line or
        refuse. MUST be called inside a transaction — the lock is worthless
        the moment it is released, and it is released at commit."""
        from app.procurement.models import ShipmentLine

        # select_for_update is the whole point: it serialises concurrent
        # linkers against this line so the read-then-write below is atomic.
        line = ShipmentLine.objects.select_for_update().select_related(
            "shipment", "part"
        ).get(pk=shipment_line_id)

        rows = live_allocations_for_line(shipment_line_id)
        if exclude_allocation_id is not None:
            rows = rows.exclude(pk=exclude_allocation_id)
        linked = rows.aggregate(t=Sum("quantity"))["t"] or ZERO
        expected = line.quantity or ZERO
        remaining = max(expected - linked, ZERO)

        if quantity > remaining:
            raise LineCapacityExceeded(
                shipment_line_id=shipment_line_id,
                part_number=line.part.part_number,
                expected=expected,
                already_linked=linked,
                requested=quantity,
            )
        return line

    @classmethod
    def fits(cls, *, shipment_line_id: int, quantity: Decimal) -> bool:
        """Non-locking pre-check for the auto-association policy, which must
        never raise at an operator (§5.3). The authoritative check is still
        `_assert_capacity` under the lock — this only avoids attempting a
        link that is obviously hopeless."""
        return quantity <= cls.remaining_capacity(shipment_line_id=shipment_line_id)

    # ------------------------------------------------------------------ #
    # Writes — the only two verbs that touch ItemAllocation.shipment_line
    # ------------------------------------------------------------------ #

    @classmethod
    def link(
        cls,
        *,
        allocation: ItemAllocation,
        shipment_line_id: int,
        link_source: str = AllocationLinkSource.MANUAL,
        actor=None,
    ) -> ItemAllocation:
        """Point one allocation at one shipment line, under the ban."""
        with transaction.atomic():
            cls._assert_capacity(
                shipment_line_id=shipment_line_id,
                quantity=allocation.quantity,
                exclude_allocation_id=allocation.pk,
            )
            allocation.shipment_line_id = shipment_line_id
            allocation.link_source = link_source
            allocation.linked_at = timezone.now()
            allocation.linked_by = actor
            allocation.updated_by = actor
            allocation.save(
                update_fields=[
                    "shipment_line", "link_source", "linked_at", "linked_by",
                    "updated_by", "updated_at",
                ]
            )
        return allocation

    @classmethod
    def unlink(cls, *, allocation: ItemAllocation, actor=None) -> ItemAllocation:
        """Return an allocation to the unlinked pool. Always permitted —
        removing quantity from a line can never violate the ban, and unlinked
        is an ordinary state rather than a punishment."""
        allocation.shipment_line = None
        allocation.link_source = AllocationLinkSource.UNLINKED
        allocation.linked_at = None
        allocation.linked_by = None
        allocation.updated_by = actor
        allocation.save(
            update_fields=[
                "shipment_line", "link_source", "linked_at", "linked_by",
                "updated_by", "updated_at",
            ]
        )
        return allocation

    @classmethod
    def set_quantity(
        cls, *, allocation: ItemAllocation, quantity: Decimal, actor=None
    ) -> ItemAllocation:
        """Resize an allocation, re-checking the ban when it is linked.

        Growing a linked row is a link write in disguise — CMDXQTY10 on a row
        sitting against a nearly-full line has to be refused for exactly the
        same reason a fresh link would be.
        """
        with transaction.atomic():
            if allocation.shipment_line_id is not None:
                cls._assert_capacity(
                    shipment_line_id=allocation.shipment_line_id,
                    quantity=quantity,
                    exclude_allocation_id=allocation.pk,
                )
            allocation.quantity = quantity
            allocation.updated_by = actor
            allocation.save(update_fields=["quantity", "updated_by", "updated_at"])
        return allocation
