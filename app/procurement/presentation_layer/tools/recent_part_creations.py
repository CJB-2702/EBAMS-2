# DELIBERATE ANTI-PATTERN (D81) — app/parts imports this procurement module, inverting
# the project's one-way parts <- procurement dependency. Accepted so that price capture
# stays wholly inside procurement without extracting a parties/ app (D79). Contained to
# the three public functions below; SESSION_KEY is private to this module and nothing
# else in the codebase may read or write it.
"""The parts-creation session breadcrumb (see parts_creation_smuggling.md).

Records which parts a user just created so the pricing grid can offer to load
them. IDs and timestamps only — no part numbers, no names, since the read path
must re-query anyway to re-authorize and drop soft-deleted parts.

Appends, never replaces (D82): one session is shared across every tab, so a
replace-semantics breadcrumb would let tab B silently destroy tab A's batch.

Nested mutation of `request.session[SESSION_KEY]` never persists — Django's
`modified` flag is only set by operations on the session object itself. Every
mutator here reads, mutates a local dict, and reassigns the whole key.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from django.http import HttpRequest

from app.procurement.presentation_layer.search.part_visibility import visible_parts_qs

SESSION_KEY = "procurement_recent_part_creations"

MAX_PARTS = 100

#: Placeholder — the real bound on breadcrumb lifetime is an app-hardening
#: concern (SESSION_COOKIE_AGE), not this kit's. Filtered on read only.
TTL = timedelta(hours=12)


def record_created_parts(
    request: HttpRequest, *, part_ids: list[int], domain_ids_by_part: dict[int, list[int]]
) -> None:
    """Append. Dedupe by part_id keeping the earliest created_at. Prune expired.
    Fill to MAX_PARTS and set overflowed=True if there is more."""
    payload = _load(request)
    now = datetime.now(timezone.utc)
    existing_by_id = {entry["part_id"]: entry for entry in payload["parts"]}

    for part_id in part_ids:
        if part_id in existing_by_id:
            continue
        existing_by_id[part_id] = {
            "part_id": part_id,
            "created_at": now.isoformat(),
            "domain_ids": list(domain_ids_by_part.get(part_id, [])),
        }

    entries = _prune_expired(list(existing_by_id.values()))
    overflowed = len(entries) > MAX_PARTS
    _save(
        request,
        {
            "parts": entries[:MAX_PARTS],
            "overflowed": overflowed or payload["overflowed"],
            "dismissed_part_ids": payload["dismissed_part_ids"],
        },
    )


def read_recent(request: HttpRequest, *, actor) -> list[int]:
    """Prune expired, re-authorize against the actor's visible domains, drop
    missing/soft-deleted parts, return what survives — silently."""
    payload = _load(request)
    entries = _prune_expired(payload["parts"])
    part_ids = [entry["part_id"] for entry in entries]
    if not part_ids:
        return []

    from app.procurement.presentation_layer.tools.procurement_access import (
        accessible_domain_ids,
    )

    domain_ids = accessible_domain_ids(request)
    visible_ids = set(
        visible_parts_qs(domain_ids=domain_ids).filter(pk__in=part_ids).values_list("pk", flat=True)
    )
    return [part_id for part_id in part_ids if part_id in visible_ids]


def read_recent_overflowed(request: HttpRequest) -> bool:
    return bool(_load(request)["overflowed"])


def consume(request: HttpRequest, *, part_ids: list[int]) -> None:
    """Remove these part_ids after their observations are committed."""
    payload = _load(request)
    consumed = set(part_ids)
    entries = [entry for entry in payload["parts"] if entry["part_id"] not in consumed]
    dismissed = [pid for pid in payload["dismissed_part_ids"] if pid not in consumed]
    _save(
        request,
        {
            "parts": entries,
            "overflowed": payload["overflowed"] and bool(entries),
            "dismissed_part_ids": dismissed,
        },
    )


def dismiss(request: HttpRequest) -> None:
    """Door 1's Dismiss button — keyed on the current batch, not a blanket
    flag, so a part created *after* dismissal still surfaces the banner
    (D86 needs this: dismissal is a nag-suppressor, not a data hider — the
    parts stay findable via the unpriced backstop either way)."""
    payload = _load(request)
    current_ids = {entry["part_id"] for entry in payload["parts"]}
    dismissed = set(payload["dismissed_part_ids"]) | current_ids
    _save(request, {**payload, "dismissed_part_ids": sorted(dismissed)})


def visible_banner_parts(request: HttpRequest, *, actor) -> list[int]:
    """`read_recent` filtered down to parts not yet dismissed — what the
    banner should actually offer."""
    payload = _load(request)
    dismissed = set(payload["dismissed_part_ids"])
    recent = read_recent(request, actor=actor)
    return [part_id for part_id in recent if part_id not in dismissed]


def _load(request: HttpRequest) -> dict:
    raw = request.session.get(SESSION_KEY)
    if not isinstance(raw, dict):
        return {"parts": [], "overflowed": False, "dismissed_part_ids": []}
    return {
        "parts": list(raw.get("parts") or []),
        "overflowed": bool(raw.get("overflowed", False)),
        "dismissed_part_ids": list(raw.get("dismissed_part_ids") or []),
    }


def _save(request: HttpRequest, payload: dict) -> None:
    request.session[SESSION_KEY] = payload
    request.session.modified = True


def _prune_expired(entries: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - TTL
    survivors = []
    for entry in entries:
        created_at = datetime.fromisoformat(entry["created_at"])
        if created_at >= cutoff:
            survivors.append(entry)
    return survivors
