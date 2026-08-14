"""Presentation-layer access checks — the permission vocabulary and the data fence.

D62 recorded that the procurement backend shipped with zero permission checks and
that `OpenDemandSearch`'s `domain_ids` seam had no caller. This module is where
both stop being true: every procurement entrypoint routes its gate through here
rather than hand-rolling `request.user.has_perm(...)` per view.

Permission codenames are declared by Phase 0 against the `procurement` app label.
Until that migration lands, `has_perm` simply returns False for ordinary users
(superusers still pass), which fails closed — the correct direction to fail.
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from app.administration.auth_session import session_domain_ids

#: Buyer — PO create/edit, line editing, allocation and de-linking (D3),
#: submit-for-approval, place, cancel.
PERM_BUY = "procurement.buy"

#: Purchasing manager — approve or deny a PO pre-purchase. Deliberately separate
#: from PERM_BUY: placing is the Buyer's act, approval is the manager's. D2's old
#: clause letting an approve-only holder place an order is retired (Phase 0 §4).
PERM_PURCHASE_APPROVE = "procurement.purchase_approve"

#: Requester — create and edit demands. Viewing a demand never requires this;
#: anyone with domain access can read (Phase 0 §5).
PERM_REQUEST = "procurement.request"

#: Floor manager — transition demand_state/issuance_state on ANY demand in
#: their domain, not only their own.
PERM_DEMAND_MANAGE = "procurement.demand_manage"

#: Receiving staff — create shipments, advance shipment status, inspect/accept
#: lines. Declared here for completeness even though this wave (demands) never
#: gates on it.
PERM_RECEIVE = "procurement.receive"

#: D89 establish level — verify a price so it becomes what everyone else is
#: shown. Recording an (unverified) observation needs only PERM_BUY. Declared
#: as a global permission for this first cut; per-domain establish authority
#: is a # TODO(D89) at the guard's call site until admin-engineering scopes it.
PERM_PRICE_ESTABLISH = "procurement.price_establish"


def can_buy(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_BUY)


def can_approve_purchase(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_PURCHASE_APPROVE)


def can_request(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_REQUEST)


def can_manage_demand(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DEMAND_MANAGE)


def can_receive(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RECEIVE)


def require_buy(request: HttpRequest) -> None:
    """Gate a write. Raises PermissionDenied (403), never a silent no-op."""
    if not can_buy(request):
        raise PermissionDenied("Buying a purchase order requires the 'buy' permission.")


def require_purchase_approve(request: HttpRequest) -> None:
    if not can_approve_purchase(request):
        raise PermissionDenied(
            "Approving a purchase order requires the 'purchase_approve' permission."
        )


def require_request(request: HttpRequest) -> None:
    if not can_request(request):
        raise PermissionDenied("This action requires the 'request' permission.")


def require_receive(request: HttpRequest) -> None:
    """Gates shipment creation (both paths), status advance, line acceptance,
    and every mutation on the shipment edit page (Phase 0 §5)."""
    if not can_receive(request):
        raise PermissionDenied(
            "Recording or changing a shipment requires the 'receive' permission."
        )


def require_demand_manage(request: HttpRequest) -> None:
    if not can_manage_demand(request):
        raise PermissionDenied("This action requires the 'demand_manage' permission.")


def can_establish_price(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_PRICE_ESTABLISH)


def require_buy_prices(request: HttpRequest) -> None:
    """Thin alias over require_buy, named for the price-recording call site.
    Recording an observation only ever needs PERM_BUY; verifying it needs
    PERM_PRICE_ESTABLISH as well (checked separately in the guard)."""
    require_buy(request)


def can_edit_demand(request: HttpRequest, demand) -> bool:
    """D4-adjacent: field edits and approve/reject on the edit page are open to
    the Requester who owns the row, or to anyone holding demand_manage."""
    if can_manage_demand(request):
        return True
    return can_request(request) and demand.requested_by_id == request.user.pk


def can_cancel_demand(request: HttpRequest, demand) -> bool:
    """D4: a Buyer never cancels a demand. Requester (own) or demand_manage only.
    The caller must not render the Cancel control at all when this is False —
    not merely disable it."""
    return can_edit_demand(request, demand)


def accessible_domain_ids(request: HttpRequest) -> list[int]:
    """The user's data domains, snapshotted at login (D5).

    Every list, every search, and every `OpenDemandSearch` call in this sector
    passes this through. An empty list means the user has no domain access and
    therefore sees no rows — that is the intended reading, not a bug to paper
    over by skipping the filter.
    """
    return session_domain_ids(request)


def is_in_domain(request: HttpRequest, domain_id: int | None) -> bool:
    """Whether a record belongs to a domain the user can reach.

    Cross-domain records are not hidden — Phase 0 §5 requires their identifying
    data render as plain text on a page the user already has access to, with no
    link through. Templates call this to decide anchor vs. plain text.
    """
    if domain_id is None:
        return False
    return domain_id in accessible_domain_ids(request)
