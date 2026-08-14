"""Presentation-layer access checks for the Inventory mirror of Shipments (D84).

D84 introduces no new Inventory-owned permission for this pass — the rows
being edited here ARE procurement's `Shipment`/`ShipmentLine` rows, mutated
through procurement's own `ShipmentContext` verbs, so the gate that matters is
still procurement's `receive` permission (the same one
`app.procurement.presentation_layer.tools.procurement_access.require_receive`
enforces on the procurement-side pages). This module does not import that
procurement presentation-layer module directly — presentation-layer code is
app-internal by convention (per `harness/Architecture/overview.md`, only
`models` and `control_layer` are meant to be reached across the boundary) —
it re-declares the same `procurement.receive` codename check locally instead,
so Inventory's access rules stay self-contained even though they currently
happen to mirror Procurement's exactly.

Domain scoping reuses `app.administration.auth_session.session_domain_ids`
directly, since that is core/shared administration infrastructure, not
something owned by procurement.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from app.administration.auth_session import session_domain_ids

#: Same codename procurement's `receive` permission uses (D78/D83). Reused
#: rather than duplicated under a new `inventory.*` codename, because this
#: pass edits procurement's own rows through procurement's own guarded verbs
#: — there is no separate Inventory-owned write surface yet to gate
#: differently (D84).
PERM_RECEIVE = "procurement.receive"


def can_receive(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RECEIVE)


def require_receive(request: HttpRequest) -> None:
    """Gates every mutation on the inventory shipment detail/edit pages."""
    if not can_receive(request):
        raise PermissionDenied(
            "Changing a shipment requires the 'receive' permission."
        )


def accessible_domain_ids(request: HttpRequest) -> list[int]:
    """The user's data domains, snapshotted at login (D5) — same session seam
    every other sub-app's presentation layer reads from."""
    return session_domain_ids(request)


def is_in_domain(request: HttpRequest, domain_id: int | None) -> bool:
    if domain_id is None:
        return False
    return domain_id in accessible_domain_ids(request)
