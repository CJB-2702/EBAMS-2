"""The Package Reallocation Portal's session draft (Package↔PO Domain) —
Phase 5's independent mirror of reallocation_draft.py. Deliberately a
separate module/session key: the two domains never share state.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

PACKAGE_REALLOCATION_SESSION_KEY = "procurement_package_reallocation_draft"


def empty_draft(*, shipment_line_id: int, new_quantity: Decimal) -> dict:
    return {
        "shipment_line_id": int(shipment_line_id),
        "new_quantity": str(new_quantity),
        "proposed": {},
        "unlocked_this_session": [],
    }


def load(session) -> dict | None:
    raw = session.get(PACKAGE_REALLOCATION_SESSION_KEY)
    if not isinstance(raw, dict) or "shipment_line_id" not in raw:
        return None
    return raw


def save(session, draft: dict) -> None:
    session[PACKAGE_REALLOCATION_SESSION_KEY] = draft
    session.modified = True


def clear(session) -> None:
    session.pop(PACKAGE_REALLOCATION_SESSION_KEY, None)
    session.modified = True


def set_proposed(draft: dict, *, link_id: int, quantity) -> None:
    draft.setdefault("proposed", {})[str(int(link_id))] = str(quantity)


def proposed_values(draft: dict) -> dict[int, Decimal]:
    return {
        int(link_id): to_decimal(quantity) or Decimal("0")
        for link_id, quantity in (draft.get("proposed") or {}).items()
    }


def mark_unlocked(draft: dict, *, link_id: int) -> None:
    unlocked = draft.setdefault("unlocked_this_session", [])
    if int(link_id) not in unlocked:
        unlocked.append(int(link_id))


def to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
