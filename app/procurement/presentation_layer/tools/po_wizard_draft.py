"""The create-PO wizard's session draft, as the wizard accumulates it.

`PurchaseOrderDraftAdaptor` validates a *complete* draft and refuses an
incomplete one — that is exactly what you want at final submit and exactly what
you cannot use while the Buyer is still filling the page in. So the two split
cleanly:

    this module          the raw session dict, mutated across many requests,
                         never validated, never written to the database
    the adaptor          the one-shot parse/validate at final submit

Both agree on `DRAFT_SESSION_KEY` and on the dict shape the adaptor's
`to_session()` produces, so the handoff is a plain `from_dict(raw)`.

Lines are addressed BY INDEX. A draft line has no identity of its own — it is
not a row and never will be until commit — so an index is the honest handle.
Removing a line reindexes the ones after it, which is fine because every form on
the page is re-rendered from the draft on the next GET.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
    DRAFT_SESSION_KEY,
)

#: One-shot slot for a D28 cap decision that must survive the POST -> redirect ->
#: GET round trip. Popped on read, so a refresh dismisses an unanswered dialog
#: rather than re-asking forever.
CAP_DECISION_SESSION_KEY = "procurement_cap_decision"


def empty_draft() -> dict:
    return {
        "vendor_id": None,
        "domain_id": None,
        "vendor_contact": "",
        # Buyer-entered, externally sourced (Phase 0 schema change #7). Carried
        # on the draft dict rather than the adaptor's dataclass because the
        # column and the dataclass field both belong to Phase 0.
        "vendor_po_id": "",
        "order_date": None,
        "expected_delivery_date": None,
        "shipping_cost": None,
        "tax_amount": None,
        "other_amount": None,
        "notes": "",
        "lines": [],
    }


def load(session) -> dict:
    raw = session.get(DRAFT_SESSION_KEY)
    if not isinstance(raw, dict):
        return empty_draft()
    # A draft written by an older shape still opens; missing keys default.
    merged = empty_draft()
    merged.update(raw)
    merged["lines"] = list(raw.get("lines") or [])
    return merged


def save(session, draft: dict) -> None:
    session[DRAFT_SESSION_KEY] = draft
    session.modified = True


def clear(session) -> None:
    session.pop(DRAFT_SESSION_KEY, None)
    session.pop(CAP_DECISION_SESSION_KEY, None)
    session.modified = True


# ---------------------------------------------------------------------- #
# Progressive enablement — computed server-side, per multi_step_flows.md.
# A JS-only gate fails the F5 rule the moment the page is refreshed.
# ---------------------------------------------------------------------- #


def has_vendor(draft: dict) -> bool:
    return bool(draft.get("vendor_id")) and bool(draft.get("domain_id"))


def has_lines(draft: dict) -> bool:
    return bool(draft.get("lines"))


def can_submit(draft: dict) -> bool:
    """A line with zero allocations is valid (D14) — proactive and bulk
    restocking is the intended path for it — so submission gates on lines
    existing, never on every line being allocated."""
    return has_vendor(draft) and has_lines(draft)


# ---------------------------------------------------------------------- #
# Line and allocation mutation
# ---------------------------------------------------------------------- #


def new_line(
    *,
    part_id: int,
    quantity_ordered: Decimal,
    unit_cost: Decimal,
    expected_delivery_date=None,
    notes: str = "",
    unit_cost_source: str = "",
    unit_cost_confidence: str = "",
    unit_cost_asserted_at=None,
) -> dict:
    return {
        "part_id": int(part_id),
        "quantity_ordered": str(quantity_ordered),
        "unit_cost": str(unit_cost),
        "expected_delivery_date": (
            str(expected_delivery_date) if expected_delivery_date else None
        ),
        "notes": notes or "",
        "unit_cost_source": unit_cost_source or "",
        "unit_cost_confidence": unit_cost_confidence or "",
        "unit_cost_asserted_at": str(unit_cost_asserted_at) if unit_cost_asserted_at else None,
        "allocations": [],
    }


def find_line_for_part(draft: dict, part_id: int) -> int | None:
    """Index of the existing line buying this part, if any.

    One active line per part per PO (D58) is a soft rule enforced in the
    validator, but the wizard should not manufacture violations: adding demands
    for a part that already has a line grows that line rather than opening a
    second.
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


def set_allocation(line: dict, *, demand_id: int, quantity, auto_approve: bool, raise_request: bool = False) -> None:
    """One allocation per (line, demand) pairing — a Buyer who wants more edits
    the existing entry, never adds a second. Mirrors the DB's unique constraint
    so the draft cannot stage something the commit would reject."""
    for allocation in line.setdefault("allocations", []):
        if int(allocation.get("demand_id")) == int(demand_id):
            allocation["quantity_allocated"] = str(quantity)
            allocation["auto_approve"] = bool(auto_approve)
            allocation["raise_request"] = bool(raise_request)
            return
    line["allocations"].append(
        {
            "demand_id": int(demand_id),
            "quantity_allocated": str(quantity),
            "auto_approve": bool(auto_approve),
            "raise_request": bool(raise_request),
        }
    )


def remove_allocation(line: dict, *, demand_id: int) -> bool:
    allocations = line.get("allocations") or []
    for index, allocation in enumerate(allocations):
        if int(allocation.get("demand_id")) == int(demand_id):
            allocations.pop(index)
            return True
    return False


def staged_for_demand(draft: dict, *, demand_id: int, skip_line_index: int | None = None) -> Decimal:
    """How much of this demand other draft lines have already claimed.

    Without this the cap check would compare each pick against the demand's
    database outstanding alone, so a Buyer could stage the same demand twice
    across two lines and only discover the over-allocation at commit — after the
    wizard had told them both were fine.
    """
    total = Decimal("0")
    for index, line in enumerate(draft.get("lines") or []):
        if skip_line_index is not None and index == skip_line_index:
            continue
        for allocation in line.get("allocations") or []:
            if int(allocation.get("demand_id")) == int(demand_id):
                total += to_decimal(allocation.get("quantity_allocated")) or Decimal("0")
    return total


def allocated_total(line: dict) -> Decimal:
    total = Decimal("0")
    for allocation in line.get("allocations") or []:
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
