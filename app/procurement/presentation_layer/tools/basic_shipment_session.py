"""The Basic Shipment Manager's session draft (`basic_shipment_session`).

This is a PLANNING surface, not a receiving one. A Buyer reads a vendor's
shipping confirmation and lays out the boxes that are *going* to arrive. So
nothing here writes: every gesture edits a session dict, and the whole layout
is committed in one shot by BasicShipmentManagerSubmitHandler.

Two rules the shape of this module exists to serve:

- **Drag-and-drop is the fast path, never the only path.** Every mutation below
  is reachable from a plain form POST with no JavaScript, which is what makes
  the F5 rule hold. The drag layer in the template posts to these same actions.
- **Seeded state is never trusted from the client.** The session is re-seeded
  from the database on every load, and the submit handler re-derives it again
  before writing. A client-echoed "original quantity" is an input, not a fact.

Session layout, keyed by purchase order so two orders can be planned in
different tabs without trampling each other::

    request.session["basic_shipment_session"] = {
        "<po_id>": {
            "next_temp": 3,
            "shipments": [
                {"temp_id": "new-1",       # session-only card
                 "shipment_id": None,
                 "shipment_id": "...", "carrier": "...",
                 "shipped_date": "", "expected_arrival_date": "", "notes": "",
                 "lines": [{"po_line_id": 12, "quantity": "5"}]},
                {"temp_id": "pkg-88",      # seeded from the database
                 "shipment_id": 88, ...},
            ],
        }
    }

Quantities live in the session as STRINGS. `request.session` is JSON-backed and
a Decimal does not survive the round trip; converting on read keeps the money
number exact instead of laundering it through a float.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.procurement.models import Shipment, ShipmentStatus

SESSION_KEY = "basic_shipment_session"

#: A shipment at or past local delivery is a physical fact, not a plan, and is
#: locked out of this tool (D69). `Lost` is NOT a lock trigger on its own — a
#: lost box is still a plan that went wrong.
#:
#: The has_splits half of this test is gone with the column (D90). Shipment
#: structure that the planner's one-chip-per-PO-line model cannot express is
#: still refused, but it is now detected from the allocations themselves in
#: BasicShipmentManagerSubmitHandler._current_lines rather than pre-declared by
#: a flag — which also means an ordinary shipment stops being permanently
#: locked by one allocation edit that has since been undone.
_LOCKED_STATUSES = frozenset(
    {ShipmentStatus.DELIVERED_TO_LOCAL, ShipmentStatus.ACCEPTED}
)


def is_locked(shipment: Shipment) -> bool:
    return shipment.status in _LOCKED_STATUSES


def lock_reason(shipment: Shipment) -> str:
    """Why a card is red. A lock with no stated reason reads as a bug."""
    if shipment.status not in _LOCKED_STATUSES:
        return ""
    return (
        f"This shipment is read-only in the planner because it is "
        f"{shipment.get_status_display()}. Edit it on its own page instead."
    )


def to_decimal(raw) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Reading and seeding
# --------------------------------------------------------------------------- #


def load(request, *, purchase_order) -> dict:
    """The draft for this PO, seeding real shipments in on first touch.

    Seeding is a merge, not a replace: session-only cards the Buyer has already
    laid out survive, and every database-backed card is refreshed from the row
    so a shipment that got delivered in another tab shows up locked here.
    """
    all_drafts = request.session.get(SESSION_KEY) or {}
    draft = all_drafts.get(str(purchase_order.pk)) or {"next_temp": 1, "shipments": []}

    seeded = _seed_from_db(purchase_order)
    session_only = [p for p in draft["shipments"] if p.get("shipment_id") is None]

    draft["shipments"] = seeded + session_only
    draft.setdefault("next_temp", 1)

    all_drafts[str(purchase_order.pk)] = draft
    request.session[SESSION_KEY] = all_drafts
    request.session.modified = True
    return draft


def _seed_from_db(purchase_order) -> list[dict]:
    shipments = (
        Shipment.objects.filter(purchase_order=purchase_order, deleted_at__isnull=True)
        .prefetch_related(
            "lines",
            "lines__purchase_order_links",
            # Needed for the same-order test below; without it each allocation
            # costs a query to find out whose line it points at.
            "lines__purchase_order_links__purchase_order_line",
        )
        .order_by("pk")
    )
    seeded = []
    for shipment in shipments:
        # AGGREGATED BY PO LINE over ALLOCATIONS, not one chip per row. A
        # shipment may carry several allocations against the same PO line, and
        # the planner's whole model is one chip per line — showing two chips
        # for one line would invite a Buyer to edit half of a receiver's
        # deliberate allocation. The submit handler refuses such a card
        # outright; this only governs what gets displayed, and the total is the
        # honest thing to display.
        totals: dict[int, Decimal] = {}
        for line in shipment.lines.all():
            if line.deleted_at is not None:
                continue
            for link in line.purchase_order_links.all():
                if link.deleted_at is not None:
                    continue
                if (
                    link.purchase_order_line.purchase_order_id
                    != purchase_order.pk
                ):
                    # Allocations against another order's line have no chip to
                    # sit on here. They are left entirely alone — see
                    # BasicShipmentManagerSubmitHandler's diff.
                    continue
                totals[link.purchase_order_line_id] = (
                    totals.get(link.purchase_order_line_id, Decimal("0"))
                    + link.quantity_allocated
                )
        lines = [
            {"po_line_id": po_line_id, "quantity": str(quantity)}
            for po_line_id, quantity in totals.items()
        ]
        seeded.append(
            {
                "temp_id": f"pkg-{shipment.pk}",
                "shipment_id": shipment.pk,
                "shipment_number": shipment.shipment_number,
                "shipment_id": shipment.shipment_id,
                "carrier": shipment.carrier,
                "shipped_date": (
                    shipment.shipped_date.isoformat() if shipment.shipped_date else ""
                ),
                "expected_arrival_date": (
                    shipment.expected_arrival_date.isoformat()
                    if shipment.expected_arrival_date
                    else ""
                ),
                "notes": shipment.notes,
                "status": shipment.status,
                "locked": is_locked(shipment),
                "lock_reason": lock_reason(shipment),
                "lines": lines,
            }
        )
    return seeded


def save(request, *, purchase_order, draft: dict) -> None:
    all_drafts = request.session.get(SESSION_KEY) or {}
    all_drafts[str(purchase_order.pk)] = draft
    request.session[SESSION_KEY] = all_drafts
    request.session.modified = True


def discard(request, *, purchase_order) -> None:
    all_drafts = request.session.get(SESSION_KEY) or {}
    all_drafts.pop(str(purchase_order.pk), None)
    request.session[SESSION_KEY] = all_drafts
    request.session.modified = True


def find(draft: dict, temp_id: str) -> dict | None:
    return next((p for p in draft["shipments"] if p["temp_id"] == temp_id), None)


# --------------------------------------------------------------------------- #
# Mutations — session only. Nothing here touches the database.
# --------------------------------------------------------------------------- #


def add_shipment(draft: dict, *, fields: dict) -> dict:
    """Append a session-only card. THE CREATE FORM WRITES NOTHING."""
    temp_id = f"new-{draft.get('next_temp', 1)}"
    draft["next_temp"] = draft.get("next_temp", 1) + 1
    card = {
        "temp_id": temp_id,
        "shipment_id": None,
        "shipment_number": "",
        "shipment_id": fields.get("shipment_id", ""),
        "carrier": fields.get("carrier", ""),
        "shipped_date": fields.get("shipped_date", ""),
        "expected_arrival_date": fields.get("expected_arrival_date", ""),
        "notes": fields.get("notes", ""),
        "status": ShipmentStatus.AWAITING_SHIPMENT,
        "locked": False,
        "lock_reason": "",
        "lines": [],
    }
    draft["shipments"].append(card)
    return card


def update_shipment(draft: dict, *, temp_id: str, fields: dict) -> bool:
    card = find(draft, temp_id)
    if card is None or card["locked"]:
        return False
    for key in (
        "shipment_id",
        "carrier",
        "shipped_date",
        "expected_arrival_date",
        "notes",
    ):
        if key in fields:
            card[key] = fields[key]
    return True


def remove_shipment(draft: dict, *, temp_id: str) -> bool:
    """Only a session-only card can be dropped here.

    Deleting a real shipment is a destructive act with a mandatory reason and a
    soft-delete cascade — that belongs to shipment edit, not to a planner where
    a stray click would take a whole shipment with it.
    """
    card = find(draft, temp_id)
    if card is None or card["shipment_id"] is not None:
        return False
    draft["shipments"].remove(card)
    return True


def assign(draft: dict, *, temp_id: str, po_line_id: int, quantity: Decimal) -> bool:
    """Put `quantity` of a PO line into a shipment card.

    Assigning the same line twice ADDS to the existing chip rather than
    creating a second one: one card holds one chip per PO line, which is what
    keeps the seeded state and the drawn state the same shape.
    """
    card = find(draft, temp_id)
    if card is None or card["locked"] or quantity is None or quantity <= 0:
        return False
    for line in card["lines"]:
        if line["po_line_id"] == po_line_id:
            line["quantity"] = str(Decimal(line["quantity"]) + quantity)
            return True
    card["lines"].append({"po_line_id": po_line_id, "quantity": str(quantity)})
    return True


def set_quantity(draft: dict, *, temp_id: str, po_line_id: int, quantity: Decimal) -> bool:
    card = find(draft, temp_id)
    if card is None or card["locked"]:
        return False
    for line in card["lines"]:
        if line["po_line_id"] == po_line_id:
            if quantity is None or quantity <= 0:
                card["lines"].remove(line)
            else:
                line["quantity"] = str(quantity)
            return True
    return False


def unassign(draft: dict, *, temp_id: str, po_line_id: int) -> bool:
    card = find(draft, temp_id)
    if card is None or card["locked"]:
        return False
    before = len(card["lines"])
    card["lines"] = [l for l in card["lines"] if l["po_line_id"] != po_line_id]
    return len(card["lines"]) != before


def move(
    draft: dict,
    *,
    from_temp_id: str,
    to_temp_id: str,
    po_line_id: int,
    quantity: Decimal | None = None,
) -> bool:
    """The drag gesture's session equivalent: take from one card, give to
    another. Rejected outright if either end is locked."""
    source = find(draft, from_temp_id)
    target = find(draft, to_temp_id)
    if source is None or target is None or source["locked"] or target["locked"]:
        return False
    chip = next((l for l in source["lines"] if l["po_line_id"] == po_line_id), None)
    if chip is None:
        return False
    available = Decimal(chip["quantity"])
    amount = available if quantity is None else min(quantity, available)
    if amount <= 0:
        return False
    remaining = available - amount
    if remaining > 0:
        chip["quantity"] = str(remaining)
    else:
        source["lines"].remove(chip)
    return assign(draft, temp_id=to_temp_id, po_line_id=po_line_id, quantity=amount)


# --------------------------------------------------------------------------- #
# Derived figures for the left column
# --------------------------------------------------------------------------- #


def planned_by_po_line(draft: dict) -> dict[int, Decimal]:
    """How much of each PO line the CURRENT DRAFT has laid out, across every
    card including the locked ones.

    Locked cards count. A Buyer who cannot see the boxes they are not allowed
    to edit will cheerfully plan the same units a second time.
    """
    totals: dict[int, Decimal] = {}
    for card in draft["shipments"]:
        for line in card["lines"]:
            qty = to_decimal(line["quantity"]) or Decimal("0")
            totals[line["po_line_id"]] = totals.get(line["po_line_id"], Decimal("0")) + qty
    return totals
