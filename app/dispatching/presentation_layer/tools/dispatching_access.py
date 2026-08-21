"""Presentation-layer access checks for the dispatching app's UI screens —
Skills, Templates, and Reservations. Permission codenames are declared on the
owning models (app.dispatching.models.skills.*, app.dispatching.models.
templates.dispatch_template, app.dispatching.models.reservations.
asset_reservation) plus one on events.DispatchingDetail for the app-wide read
grant — see dispatching_starter_kit/5_roles_and_permissions.md §2, §4.2, §4.4.

Skills (the catalogue and certifications) carry no domain scoping — the
schema has none, and the design docs never ask for it. Templates and
reservations are domain-scoped via their own ``domain`` FK; failing the
domain fence renders as 404, never 403, matching R3 of
5_roles_and_permissions.md.
"""

from __future__ import annotations

from django.http import HttpRequest

from app.administration.auth_session import session_domain_ids

PERM_SKILLS_CATALOGUE = "dispatching.skills_catalogue"
PERM_SKILLS_CERTIFY = "dispatching.skills_certify"
PERM_TEMPLATE_AUTHOR = "dispatching.template_author"
PERM_TEMPLATE_COMMIT = "dispatching.template_commit"
PERM_DISPATCHING_READ = "events.dispatching_read"

PERM_RESERVATION_BOOK = "dispatching.reservation_book"
PERM_RESERVATION_CONFIRM = "dispatching.reservation_confirm"
PERM_RESERVATION_SELF_SERVICE = "dispatching.reservation_self_service"
PERM_RESERVATION_VERIFY = "dispatching.reservation_verify"

PERM_DISPATCH_RAISE = "events.dispatch_raise"
PERM_DISPATCH_PLAN = "events.dispatch_plan"
PERM_DISPATCH_REJECT = "events.dispatch_reject"
PERM_DISPATCH_COMPLETE = "events.dispatch_complete"


def can_raise_dispatch(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DISPATCH_RAISE)


def can_plan_dispatch(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DISPATCH_PLAN)


def can_reject_dispatch(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DISPATCH_REJECT)


def can_complete_dispatch(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DISPATCH_COMPLETE)


def can_view_dispatches(request: HttpRequest) -> bool:
    return can_read_dispatching(request) or can_raise_dispatch(request) or can_plan_dispatch(request)


def can_manage_skills_catalogue(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_SKILLS_CATALOGUE)


def can_certify_skills(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_SKILLS_CERTIFY)


def can_author_templates(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_TEMPLATE_AUTHOR)


def can_commit_templates(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_TEMPLATE_COMMIT)


def can_read_dispatching(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_DISPATCHING_READ)


def can_view_templates(request: HttpRequest) -> bool:
    """Template list/detail/history: Template — Author or Dispatching — Read
    (5_roles_and_permissions.md §4.4)."""
    return can_author_templates(request) or can_read_dispatching(request)


def can_view_skill_catalogue(request: HttpRequest) -> bool:
    """Skill detail is reachable by Skills — Catalogue *or* Dispatching —
    Read (§4.4, "Skills — Catalogue *or* Dispatching — Read")."""
    return can_manage_skills_catalogue(request) or can_read_dispatching(request)


# ─────────────────────────────────────────────────────────────────────────
# Reservations — 5_roles_and_permissions.md §4.2
# ─────────────────────────────────────────────────────────────────────────

def can_book_reservations(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RESERVATION_BOOK)


def can_confirm_reservations(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RESERVATION_CONFIRM)


def can_self_service_reservations(request: HttpRequest) -> bool:
    return request.user.has_perm(PERM_RESERVATION_SELF_SERVICE)


def can_verify_handover(request: HttpRequest) -> bool:
    """Dispatcher-side checkout and return verification (Reservation —
    Verify). §4.2: "Verify handover / return | Reservation — Verify"."""
    return request.user.has_perm(PERM_RESERVATION_VERIFY)


def is_dispatch_manager(request: HttpRequest) -> bool:
    """The Dispatch Manager role has no permission of its own — it is a child
    role of Dispatcher defined purely as a bundle (§3). Template — Commit is
    the group it holds that no other role does, so it is the sharpest
    available marker for "is this person a dispatch manager".

    Used for one thing only: letting a manager record the *user* side of a
    handover on someone else's behalf (see can_self_service_for below). If a
    dedicated Reservation — Administer permission is ever added, point this
    at it instead.
    """
    return request.user.has_perm(PERM_TEMPLATE_COMMIT)


def can_view_reservations(request: HttpRequest) -> bool:
    """List, calendar, and detail. §4.2: "Asset calendar | Dispatching — Read
    **or** Reservation — Book — availability must be widely visible or nobody
    can self-serve"."""
    return can_read_dispatching(request) or can_book_reservations(request)


def can_self_service_for(request: HttpRequest, reservation) -> bool:
    """The user-reported handover track. The accountable person always may;
    a dispatch manager may record it on their behalf.

    §4.5 originally made this accountable-person-only. That is relaxed here
    deliberately — a manager standing at the gate must be able to record what
    the user reported without impersonating them. VerifierDistinctPolicy
    still stops the same person from then verifying their own entry, which is
    the constraint the two-track design actually depends on.
    """
    if not can_self_service_reservations(request):
        return False
    return reservation.accountable_person_id == request.user.pk or is_dispatch_manager(request)


def can_administer_reservations(request: HttpRequest) -> bool:
    """The edit-every-field screen. Dispatch managers only — this route
    writes fields no lifecycle verb exposes, so it sits above the ordinary
    dispatcher grants."""
    return is_dispatch_manager(request)


def accessible_domain_ids(request: HttpRequest) -> list[int]:
    """The user's data domains, snapshotted at login (D5)."""
    return session_domain_ids(request)


def is_in_domain(request: HttpRequest, domain_id: int | None) -> bool:
    if domain_id is None:
        return False
    return domain_id in accessible_domain_ids(request)
