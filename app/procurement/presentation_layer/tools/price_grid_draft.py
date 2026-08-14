"""The bulk price-observation grid's session draft, mirrors po_wizard_draft.py.

A separate session key from the parts-creation breadcrumb
(recent_part_creations.py) — conflating them lets a half-typed grid
resurrect already-priced parts. The dict shape matches
`PartPriceGridAdaptor.to_session()`'s output plus the batch header, so the
handoff between the two is a plain merge.
"""

from __future__ import annotations

DRAFT_SESSION_KEY = "procurement_price_grid_draft"


def empty_draft() -> dict:
    return {
        "vendor_id": None,
        "domain_id": None,
        "observed_at": None,
        "source_type": "",
        "confidence": "",
        "notes": "",
        "record_as_verified": False,
        "rows": [],
    }


def load(session) -> dict:
    raw = session.get(DRAFT_SESSION_KEY)
    if not isinstance(raw, dict):
        return empty_draft()
    merged = empty_draft()
    merged.update(raw)
    merged["rows"] = list(raw.get("rows") or [])
    return merged


def save(session, draft: dict) -> None:
    session[DRAFT_SESSION_KEY] = draft
    session.modified = True


def clear(session) -> None:
    session.pop(DRAFT_SESSION_KEY, None)
    session.modified = True


def set_header(
    draft: dict,
    *,
    vendor_id=None,
    domain_id=None,
    observed_at=None,
    source_type=None,
    confidence=None,
    notes=None,
    record_as_verified=None,
) -> None:
    if vendor_id is not None:
        draft["vendor_id"] = vendor_id
    if domain_id is not None:
        draft["domain_id"] = domain_id
    if observed_at is not None:
        draft["observed_at"] = observed_at
    if source_type is not None:
        draft["source_type"] = source_type
    if confidence is not None:
        draft["confidence"] = confidence
    if notes is not None:
        draft["notes"] = notes
    if record_as_verified is not None:
        draft["record_as_verified"] = record_as_verified


def add_rows(draft: dict, *, part_ids: list[int]) -> None:
    """Additive — the three doors never replace what's already in the grid.
    A part already present is not added twice."""
    existing = {row["part_id"] for row in draft["rows"]}
    for part_id in part_ids:
        if part_id in existing:
            continue
        draft["rows"].append({"part_id": part_id, "quantity": "", "unit_cost": ""})
        existing.add(part_id)


def remove_row(draft: dict, *, part_id: int) -> bool:
    rows = draft["rows"]
    for index, row in enumerate(rows):
        if row["part_id"] == part_id:
            rows.pop(index)
            return True
    return False


def set_row_values(draft: dict, *, part_id: int, quantity: str, unit_cost: str) -> None:
    for row in draft["rows"]:
        if row["part_id"] == part_id:
            row["quantity"] = quantity
            row["unit_cost"] = unit_cost
            return
