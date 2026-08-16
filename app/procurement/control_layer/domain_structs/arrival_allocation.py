"""Struct helpers: turning shipment-line allocations into per-PO-line numbers.

--------------------------------------------------------------------------
THE ONE PLACE A QUANTITY IS EVER DIVIDED (D90). Read this before changing it.
--------------------------------------------------------------------------

Two questions get asked of a PO line once shipments start arriving, and they
have very different epistemic status.

  "How much has been SHIPPED against this line?"
      EXACT. It is the sum of quantity_allocated on the line's active
      allocations. A human decided each of those numbers deliberately, on a
      specific arriving line, and recorded it. Nothing is inferred.

  "How much has been ACCEPTED against this line?"
      DERIVED, BY PRORATION. Inspection happens once, physically, to the
      arriving line as a whole — 120 turned up, 114 passed. If that line is
      allocated 100/20 across two PO lines, nobody inspected "the hundred" or
      "the twenty" separately. The six rejected units are somewhere in the
      box and the box does not remember.

D55 forbids exactly this kind of division on the DEMAND side, and that
prohibition stands: the system must never split a shared session's arrivals
among its member demands. This is a different case, and the difference is
worth stating precisely rather than treating the two as one rule:

  - On the demand side, the allocation is a CLAIM on future fungible units.
    Nobody has decided whose units are whose, and the division has no
    referent at all — inventing one manufactures a fact.
  - Here, the allocation is a RECORDING of a physical mapping that a receiver
    already made. The division has a referent; only the acceptance shortfall
    within it is unobserved, and proportional spreading is the one treatment
    that is symmetric across allocations, order-independent, and sums back to
    the physical total exactly.

That is a real weakening, not a free pass, and it is confined here so it stays
findable. A line with ONE allocation — overwhelmingly the common case, and
always the case when the whole arriving line answers a single order — takes
its accepted quantity whole and is not prorated at all. Proration only ever
touches the multi-allocation minority. If a business later needs exact
per-PO-line acceptance, the answer is a per-allocation inspection column here,
not a better formula; this module is the seam that change goes through.

The unallocated remainder never receives a share. Units nobody has assigned to
an order are not silently credited to one.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.models import PurchaseOrderShipmentLink, ShipmentLine

ZERO = Decimal("0")


def allocated_by_purchase_order_line(
    *, purchase_order_line_ids
) -> dict[int, Decimal]:
    """Shipped quantity allocated to each PO line. EXACT — no inference."""
    ids = list(purchase_order_line_ids)
    if not ids:
        return {}
    totals: dict[int, Decimal] = {}
    for po_line_id, quantity in _active_links(ids).values_list(
        "purchase_order_line_id", "quantity_allocated"
    ):
        totals[po_line_id] = totals.get(po_line_id, ZERO) + quantity
    return totals


def accepted_by_purchase_order_line(
    *, purchase_order_line_ids
) -> dict[int, Decimal]:
    """Accepted quantity attributable to each PO line.

    Exact for any arriving line with a single allocation; PRORATED BY
    ALLOCATION SHARE across the allocations of a line that answers several PO
    lines. See the module docstring — this is the only division in the app.

    An uninspected arriving line (quantity_accepted is NULL) contributes
    nothing, which is different from contributing zero and is why the null is
    skipped rather than coalesced.
    """
    ids = list(purchase_order_line_ids)
    if not ids:
        return {}

    links = list(
        _active_links(ids)
        .select_related("shipment_line")
        .filter(shipment_line__quantity_accepted__isnull=False)
    )
    if not links:
        return {}

    # Total ACTIVE allocation per arriving line — the denominator of the
    # share. Deliberately not the line's own `quantity`: allocations may cover
    # only part of the box, and the unallocated remainder must not absorb a
    # slice of the accepted total.
    allocated_per_shipment_line: dict[int, Decimal] = {}
    for link in _active_links_for_shipment_lines(
        {link.shipment_line_id for link in links}
    ):
        allocated_per_shipment_line[link.shipment_line_id] = (
            allocated_per_shipment_line.get(link.shipment_line_id, ZERO)
            + link.quantity_allocated
        )

    totals: dict[int, Decimal] = {}
    for link in links:
        denominator = allocated_per_shipment_line.get(link.shipment_line_id, ZERO)
        if denominator <= 0:
            continue
        accepted = link.shipment_line.quantity_accepted
        share = (accepted * link.quantity_allocated) / denominator
        totals[link.purchase_order_line_id] = (
            totals.get(link.purchase_order_line_id, ZERO) + share
        )
    return totals


def allocated_by_shipment_line(*, shipment_line_ids) -> dict[int, Decimal]:
    """Total active allocation per arriving line — the number the unallocated
    remainder is computed against."""
    ids = list(shipment_line_ids)
    if not ids:
        return {}
    totals: dict[int, Decimal] = {}
    for link in _active_links_for_shipment_lines(ids):
        totals[link.shipment_line_id] = (
            totals.get(link.shipment_line_id, ZERO) + link.quantity_allocated
        )
    return totals


def unallocated_remainder(*, shipment_line: ShipmentLine) -> Decimal:
    """What arrived that nobody has pointed at an order line yet.

    A REAL BUSINESS STATE, not a discrepancy — see PurchaseOrderShipmentLink's
    docstring. Never negative: the allocation validator caps the sum at the
    line's quantity.
    """
    allocated = allocated_by_shipment_line(shipment_line_ids=[shipment_line.pk]).get(
        shipment_line.pk, ZERO
    )
    remainder = shipment_line.quantity - allocated
    return remainder if remainder > 0 else ZERO


def _active_links(purchase_order_line_ids):
    return PurchaseOrderShipmentLink.objects.filter(
        purchase_order_line_id__in=purchase_order_line_ids,
        deleted_at__isnull=True,
        shipment_line__deleted_at__isnull=True,
    )


def _active_links_for_shipment_lines(shipment_line_ids):
    return PurchaseOrderShipmentLink.objects.filter(
        shipment_line_id__in=list(shipment_line_ids),
        deleted_at__isnull=True,
        shipment_line__deleted_at__isnull=True,
    )
