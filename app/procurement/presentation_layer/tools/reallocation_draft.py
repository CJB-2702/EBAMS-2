"""The Reallocation Portal's session draft (Demand↔PO Domain).

Same shape as po_wizard_draft.py: a plain dict, mutated across many requests,
never itself the source of truth. UNLIKE the wizard draft, this one is
RE-DERIVED FROM LIVE DB STATE on every load — reallocation_resolution_portal.md
§10 point 3 requires every screen in this flow to reflect the true current
total at view time and at submit time, with no cached number that can go
stale. So this module only ever remembers the Buyer's IN-PROGRESS proposed
values (what they've typed or the waterfall has proposed) and which claims
they've deliberately unlocked THIS session — never a claim total, a locked
total, or anything else recomputed cheaply from the database.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

REALLOCATION_SESSION_KEY = "procurement_reallocation_draft"


def empty_draft(*, line_id: int, new_quantity_ordered: Decimal) -> dict:
    return {
        "line_id": int(line_id),
        "new_quantity_ordered": str(new_quantity_ordered),
        # {link_id: proposed_quantity_allocated}, OPEN claims only.
        "proposed": {},
        # Claim ids unlocked this Portal session via the two-popup sequence —
        # never written back to "locked" automatically; only a fresh
        # record_receipt or a brand-new session can relock one.
        "unlocked_this_session": [],
    }


def load(session) -> dict | None:
    raw = session.get(REALLOCATION_SESSION_KEY)
    if not isinstance(raw, dict) or "line_id" not in raw:
        return None
    return raw


def save(session, draft: dict) -> None:
    session[REALLOCATION_SESSION_KEY] = draft
    session.modified = True


def clear(session) -> None:
    session.pop(REALLOCATION_SESSION_KEY, None)
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


def is_unlocked_this_session(draft: dict, *, link_id: int) -> bool:
    return int(link_id) in (draft.get("unlocked_this_session") or [])


# --------------------------------------------------------------------- #
# Two-popup unlock sequence (§6): a claim id parked here between the first
# call (server warns, writes nothing) and the second (`confirmed=1`). Purely
# UI-routing state — which claim is awaiting the second popup on the NEXT
# render — never a business fact, and cleared the moment any other portal
# action is taken so a stale confirmation dialog cannot reappear after the
# user has moved on to auto-allocate/manual entry/a fresh unlock attempt.
# --------------------------------------------------------------------- #


def set_pending_unlock(draft: dict, *, link_id: int) -> None:
    draft["pending_unlock_link_id"] = int(link_id)


def clear_pending_unlock(draft: dict) -> None:
    draft.pop("pending_unlock_link_id", None)


def pending_unlock_link_id(draft: dict) -> int | None:
    value = draft.get("pending_unlock_link_id")
    return int(value) if value is not None else None


def to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
