"""The create-shipment wizard's session draft, as the wizard accumulates it.

The direct mirror of `po_wizard_draft`, one level down the chain: where the PO
wizard stages lines and links each to PART DEMANDS, this stages arriving lines
and links each to PURCHASE ORDER LINES. Same shape, same rules, same reason for
existing — nothing is written until the final submit, so an abandoned draft
leaves no half-built shipment for another receiver to trip over.

Lines are addressed BY INDEX for the same reason they are there: a draft line is
not a row and has no identity until commit. Allocations inside a line are keyed
by `purchase_order_line_id`, one per pairing, mirroring the DB's unique
constraint so the draft cannot stage something the commit would reject.

THE ONE RULE THIS MODULE ENFORCES that the PO wizard's has no equivalent of:
a line's staged allocations may never total more than the line's own quantity.
That is `ShipmentLineValidator.check_allocation`'s cap — the thing that keeps
the link table honest (D90) — and it is checked here too so the wizard refuses
the pick rather than letting the Buyer discover it at submit.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

#: Session slot. Distinct from the Basic Shipment Manager's per-PO draft — that
#: one plans several expected boxes for one order; this one builds one box.
DRAFT_SESSION_KEY = "procurement_shipment_draft"


def empty_draft() -> dict:
    return {
        # Optional (D71/D73): a shipment may be created against an order, or
        # against none at all with only a domain to fence it.
        "purchase_order_id": None,
        "domain_id": None,
        "shipment_id": "",
        "carrier": "",
        "shipped_date": None,
        "expected_arrival_date": None,
        "notes": "",
        "lines": [],
    }


def load(session) -> dict:
    raw = session.get(DRAFT_SESSION_KEY)
    if not isinstance(raw, dict):
        return empty_draft()
    merged = empty_draft()
    merged.update(raw)
    merged["lines"] = list(raw.get("lines") or [])
    return merged


def save(session, draft: dict) -> None:
    session[DRAFT_SESSION_KEY] = draft
    session.modified = True


def clear(session) -> None:
    session.pop(DRAFT_SESSION_KEY, None)
    session.modified = True


# ---------------------------------------------------------------------- #
# Progressive enablement — computed server-side, per multi_step_flows.md.
# A JS-only gate fails the F5 rule the moment the page is refreshed.
# ---------------------------------------------------------------------- #


def has_header(draft: dict) -> bool:
    """A shipment needs SOMEWHERE to live before its contents can be picked.

    Either an order (whose domain it inherits) or a domain of its own. The PO
    wizard's equivalent gate wants vendor AND domain; here the order supplies
    the domain, so one or the other is enough.
    """
    return bool(draft.get("purchase_order_id")) or bool(draft.get("domain_id"))


def has_lines(draft: dict) -> bool:
    return bool(draft.get("lines"))


def can_submit(draft: dict) -> bool:
    """A line with zero allocations is valid — a substitution, a bonus item, or
    a box whose paperwork has not caught up — so submission gates on lines
    existing, never on every line being allocated."""
    return has_header(draft) and has_lines(draft)


# ---------------------------------------------------------------------- #
# Line and allocation mutation
# ---------------------------------------------------------------------- #


def new_line(*, part_id: int, quantity: Decimal, notes: str = "") -> dict:
    return {
        "part_id": int(part_id),
        "quantity": str(quantity),
        "notes": notes or "",
        "allocations": [],
    }


def find_line_for_part(draft: dict, part_id: int) -> int | None:
    """Index of the existing arriving line for this part, if any.

    One line per part per shipment while the wizard is staging — picking a
    second order line for a part the box already contains grows nothing and
    allocates against the SAME physical line, which is the whole point of the
    link table: one arriving line can answer several orders.
    """
    for index, line in enumerate(draft.get("lines") or []):
        if int(line.get("part_id") or 0) == int(part_id):
            return index
    return None


def line_at(draft: dict, index: int) -> dict | None:
    lines = draft.get("lines") or []
    if 0 <= index < len(lines):
        return lines[index]
    return None


def remove_line(draft: dict, index: int) -> bool:
    lines = draft.get("lines") or []
    if 0 <= index < len(lines):
        lines.pop(index)
        return True
    return False


def set_allocation(line: dict, *, purchase_order_line_id: int, quantity) -> None:
    """One allocation per (line, PO line) pairing — a receiver who wants a
    different amount edits the existing entry, never adds a second. Mirrors the
    unique constraint on `PurchaseOrderShipmentLink`."""
    for allocation in line.setdefault("allocations", []):
        if int(allocation.get("purchase_order_line_id")) == int(purchase_order_line_id):
            allocation["quantity_allocated"] = str(quantity)
            return
    line["allocations"].append(
        {
            "purchase_order_line_id": int(purchase_order_line_id),
            "quantity_allocated": str(quantity),
        }
    )


def remove_allocation(line: dict, *, purchase_order_line_id: int) -> bool:
    allocations = line.get("allocations") or []
    for index, allocation in enumerate(allocations):
        if int(allocation.get("purchase_order_line_id")) == int(purchase_order_line_id):
            allocations.pop(index)
            return True
    return False


def allocated_total(line: dict, *, skip_purchase_order_line_id: int | None = None) -> Decimal:
    """How much of this arriving line is already spoken for.

    `skip_purchase_order_line_id` excludes the pairing being rewritten, so
    raising an existing allocation is checked against the same headroom as a
    new one — the same exclusion `ShipmentLineManager.allocate` performs
    against the database.
    """
    total = Decimal("0")
    for allocation in line.get("allocations") or []:
        if (
            skip_purchase_order_line_id is not None
            and int(allocation.get("purchase_order_line_id"))
            == int(skip_purchase_order_line_id)
        ):
            continue
        total += to_decimal(allocation.get("quantity_allocated")) or Decimal("0")
    return total


def unallocated(line: dict) -> Decimal:
    quantity = to_decimal(line.get("quantity")) or Decimal("0")
    return quantity - allocated_total(line)


def staged_for_purchase_order_line(
    draft: dict, *, purchase_order_line_id: int, skip_line_index: int | None = None
) -> Decimal:
    """How much of this ORDER line other draft lines have already claimed.

    Used for the over-receipt warning only. Unlike the arriving line's cap this
    never blocks: vendors over-ship, and the honest record says so
    (`ShipmentLineValidator.check_acceptance`'s reasoning applies here too).
    """
    total = Decimal("0")
    for index, line in enumerate(draft.get("lines") or []):
        if skip_line_index is not None and index == skip_line_index:
            continue
        for allocation in line.get("allocations") or []:
            if int(allocation.get("purchase_order_line_id")) == int(
                purchase_order_line_id
            ):
                total += to_decimal(allocation.get("quantity_allocated")) or Decimal("0")
    return total


# ---------------------------------------------------------------------- #


def to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
