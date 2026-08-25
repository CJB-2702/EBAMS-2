"""The purchasing queue — "I noticed this needs buying, deal with it later".

A plain list of demand ids parked in the session, filled from
`/procurement/demands/`'s bulk action bar and drained by the PO create wizard,
which hands the whole list straight to its existing `add_from_demands` handler.

Deliberately NOT a draft: it stores ids and nothing else. Quantities, unit
costs, and line grouping are the wizard's business and it already knows how to
derive them (`_wizard_add_from_demands`) — duplicating any of that here would
be a second source of truth for the same decision.

Mirrors `app.inventory.presentation_layer.tools.issuance_draft`'s shape so the
two topnav queue badges read identically.
"""

from __future__ import annotations

from django.http import HttpRequest

from app.procurement.models import PartDemand

SESSION_KEY_PREFIX = "purchasing_queue_"


def session_key(request: HttpRequest) -> str:
    return f"{SESSION_KEY_PREFIX}{request.user.pk}"


def load(request: HttpRequest) -> list[int]:
    if not request.user.is_authenticated:
        return []
    return request.session.get(session_key(request), [])


def save(request: HttpRequest, demand_ids: list[int]) -> None:
    request.session[session_key(request)] = demand_ids
    request.session.modified = True


def clear(request: HttpRequest) -> None:
    save(request, [])


def count(request: HttpRequest) -> int:
    """Topnav badge's read — a dict lookup and a len(), no database."""
    return len(load(request))


def add(request: HttpRequest, *, demand_ids, domain_ids) -> tuple[int, int]:
    """Queue demands for purchasing. Returns (added, skipped).

    Skipped covers both "already queued" and "not in your domains" — the
    caller reports a count, not a per-id verdict, because the bulk bar's
    message has no room for one and the fence must not confirm which ids
    exist outside it.
    """
    wanted = [d for d in (_to_int(v) for v in demand_ids) if d]
    if not wanted:
        return (0, 0)

    allowed = set(
        PartDemand.objects.filter(
            pk__in=wanted, domain_id__in=domain_ids, deleted_at__isnull=True
        ).values_list("pk", flat=True)
    )

    queued = load(request)
    existing = set(queued)
    added = 0
    for demand_id in wanted:
        if demand_id in allowed and demand_id not in existing:
            queued.append(demand_id)
            existing.add(demand_id)
            added += 1

    save(request, queued)
    return (added, len(wanted) - added)


def remove(request: HttpRequest, *, demand_id: int) -> bool:
    queued = load(request)
    demand_id = _to_int(demand_id)
    if demand_id in queued:
        queued.remove(demand_id)
        save(request, queued)
        return True
    return False


def remove_many(request: HttpRequest, *, demand_ids) -> int:
    """Drain the ids the wizard actually consumed, leaving anything it
    skipped (nothing outstanding, out of domain) queued and visible."""
    drop = {d for d in (_to_int(v) for v in demand_ids) if d}
    if not drop:
        return 0
    queued = load(request)
    kept = [d for d in queued if d not in drop]
    removed = len(queued) - len(kept)
    if removed:
        save(request, kept)
    return removed


def demands(request: HttpRequest, *, domain_ids) -> list[PartDemand]:
    """Hydrate the queue for display — the topnav popover and the wizard's
    banner both render off this.

    Re-applies the domain fence on read, not just on write: a user's domain
    assignments can change while a queue sits in their session.
    """
    queued = load(request)
    if not queued:
        return []
    rows = {
        d.pk: d
        for d in PartDemand.objects.filter(
            pk__in=queued, domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("part", "domain", "requested_by")
    }
    # Preserve the order the user queued them in.
    return [rows[pk] for pk in queued if pk in rows]


def _to_int(raw) -> int | None:
    if raw is None:
        return None
    raw = str(raw).strip()
    return int(raw) if raw.isdigit() else None
