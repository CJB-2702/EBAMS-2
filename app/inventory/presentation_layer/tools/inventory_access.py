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

#: Phase 4 — Intake is genuinely Inventory-owned (it writes ActiveInventory,
#: not procurement rows directly), so it gets its own codename:
#: `Warehouse.Meta.permissions`'s `can_intake_stock`.
PERM_INTAKE = "inventory.can_intake_stock"

#: Phase 6 — movement and issuance are each their own codename on
#: `Warehouse.Meta.permissions`, mirroring `PERM_INTAKE`'s shape.
PERM_MOVE = "inventory.can_move_stock"
PERM_ISSUE = "inventory.can_issue_parts"

#: Phase 7 — auditing (room/spot count sessions, inline edits) is its own
#: codename on `Warehouse.Meta.permissions`, mirroring `PERM_INTAKE`'s shape.
PERM_AUDIT = "inventory.can_audit_stock"

#: Storeroom-designer port — creating/editing/retiring warehouses, rooms, and
#: their XY/Z locations, plus uploading layout SVGs. The legacy app gated its
#: storeroom designer only on `@require_any_module_role('supply')` (and half
#: its routes on nothing but `@login_required`); this port puts every write
#: behind the app's own `can_manage_topography` codename.
PERM_TOPOGRAPHY = "inventory.can_manage_topography"


def can_receive(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RECEIVE)


def require_receive(request: HttpRequest) -> None:
    """Gates every mutation on the inventory shipment detail/edit pages."""
    if not can_receive(request):
        raise PermissionDenied(
            "Changing a shipment requires the 'receive' permission."
        )


def can_intake(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_INTAKE)


def require_intake(request: HttpRequest) -> None:
    """Gates every mutation on the Intake dashboard/Auto Intake portal."""
    if not can_intake(request):
        raise PermissionDenied(
            "Receiving stock requires the 'can_intake_stock' permission."
        )


def can_move(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_MOVE)


def require_move(request: HttpRequest) -> None:
    """Gates every mutation on the movement portal / putaway worklist."""
    if not can_move(request):
        raise PermissionDenied(
            "Moving stock requires the 'can_move_stock' permission."
        )


def can_issue(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_ISSUE)


def require_issue(request: HttpRequest) -> None:
    """Gates every mutation on the issuance portal."""
    if not can_issue(request):
        raise PermissionDenied(
            "Issuing parts requires the 'can_issue_parts' permission."
        )


def can_audit(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_AUDIT)


def require_audit(request: HttpRequest) -> None:
    """Gates every mutation on the audit dashboard / count portal / inline
    edit control."""
    if not can_audit(request):
        raise PermissionDenied(
            "Auditing stock requires the 'can_audit_stock' permission."
        )


def can_manage_topography(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_TOPOGRAPHY)


def require_manage_topography(request: HttpRequest) -> None:
    """Gates every write on the warehouse CRUD pages and both tiers of the
    layout builder."""
    if not can_manage_topography(request):
        raise PermissionDenied(
            "Managing warehouses and storage locations requires the "
            "'can_manage_topography' permission."
        )


def accessible_domain_ids(request: HttpRequest) -> list[int]:
    """The user's data domains, snapshotted at login (D5) — same session seam
    every other sub-app's presentation layer reads from."""
    return session_domain_ids(request)


def is_in_domain(request: HttpRequest, domain_id: int | None) -> bool:
    if domain_id is None:
        return False
    return domain_id in accessible_domain_ids(request)
