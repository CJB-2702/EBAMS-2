"""The "Issue Parts from a Location" portal's own staging queue.

SEPARATE FROM `issuance_draft` ON PURPOSE. That module backs the demand-first
bulk portal and its lines are demand-anchored by definition; this one backs the
spatial single-grab portal, where the user walks the map to a shelf, takes the
thing, and may or may not have a demand to hang it on.

The two used to share one session key, and the cost was that every consumer had
to work out which of three line shapes it was holding from which keys happened
to be set. Two keys, two shapes, no discrimination — see
`docs/inventory/issuance_portal_separation.md`.

Line shape here is the wide one, because a grab may be anchored any of the three
ways `PartIssue` supports:

    {"issue_type", "demand_id", "issued_to_asset_id",
     "active_inventory_id", "quantity", "notes"}

There is no recipient on a line: the receipt's header owns that, and one
handover has one recipient.
"""

from __future__ import annotations

from django.http import HttpRequest

SESSION_KEY_PREFIX = "location_issuance_draft_"


def session_key(request: HttpRequest) -> str:
    return f"{SESSION_KEY_PREFIX}{request.user.pk}"


def load(request: HttpRequest) -> list[dict]:
    if not request.user.is_authenticated:
        return []
    return request.session.get(session_key(request), [])


def save(request: HttpRequest, lines: list[dict]) -> None:
    request.session[session_key(request)] = lines
    request.session.modified = True


def clear(request: HttpRequest) -> None:
    save(request, [])
