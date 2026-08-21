"""URL configuration for the dispatching app.

Pass 1 (build_phase_3_ui.md): the module shell, the skills catalogue and
certifications, and dispatch templates (lineage + session-backed draft
editor).

Reservations were brought forward from pass 2 — they are the only operational
part of the module that works with no dispatch in the database at all
(HANDOFF.md §5), so the booking surface can be finished and used before the
dispatcher queue exists. The dispatch queue, dispatch create/edit, and
expenses remain unbuilt.

Reservation routes are singular (``/reservation/<id>``) and plural for the
index (``/reservations``). Detail, each handover step, and edit are separate
routes over one record rather than density variants of one page: each is a
different job with its own permission gate and its own audience, which is the
case the single-canonical-URL rule does not cover.
"""

from __future__ import annotations

from django.urls import path

from app.dispatching.presentation_layer.entrypoints.requirement_pool_views import (
    capability_pool_search,
    configuration_template_pool_search,
    material_pool_search,
)
from app.dispatching.presentation_layer.entrypoints.reservation_views import (
    reservation_asset_search,
    reservation_create,
    reservation_detail,
    reservation_dispatcher_checkin,
    reservation_dispatcher_checkout,
    reservation_edit,
    reservation_index,
    reservation_lifecycle,
    reservation_user_checkin,
    reservation_user_checkout,
)
from app.dispatching.presentation_layer.entrypoints.shell import dispatching_hub
from app.dispatching.presentation_layer.entrypoints.skill_views import (
    certification_certify,
    certification_revoke,
    certification_update,
    my_certifications,
    skill_create,
    skill_detail,
    skill_edit,
    skill_index,
    skill_toggle_active,
    skills_linkage_portal,
    user_skills,
)
from app.dispatching.presentation_layer.entrypoints.template_views import (
    template_detail,
    template_draft_commit,
    template_draft_editor,
    template_draft_start_copy,
    template_draft_start_edit,
    template_draft_start_new,
    template_draft_update,
    template_index,
    template_reinstate,
    template_retire,
)

from app.dispatching.presentation_layer.entrypoints.dispatch_views import (
    dispatch_attach_reservation,
    dispatch_cancel,
    dispatch_create,
    dispatch_crew_action,
    dispatch_demand_action,
    dispatch_detail,
    dispatch_edit,
    dispatch_expense_action,
    dispatch_index,
    dispatch_lifecycle,
    dispatch_personnel_search,
    dispatch_reject,
    dispatch_requirement_action,
    dispatch_supersede,
    dispatch_update_intent,
)

urlpatterns = [
    path("", dispatching_hub, name="dispatching_hub"),

    # ── Dispatches ───────────────────────────────────────────────────────
    path("dispatches", dispatch_index, name="dispatching_dispatch_index"),
    path("dispatches/create", dispatch_create, name="dispatching_dispatch_create"),
    path("dispatch/<int:pk>", dispatch_detail, name="dispatching_dispatch_detail"),
    path("dispatch/<int:pk>/edit", dispatch_edit, name="dispatching_dispatch_edit"),
    path("dispatch/<int:pk>/lifecycle", dispatch_lifecycle, name="dispatching_dispatch_lifecycle"),
    path("dispatch/<int:pk>/intent", dispatch_update_intent, name="dispatching_dispatch_update_intent"),
    path("dispatch/<int:pk>/requirements", dispatch_requirement_action, name="dispatching_dispatch_requirement_action"),
    path("dispatch/<int:pk>/demands", dispatch_demand_action, name="dispatching_dispatch_demand_action"),
    path("dispatch/<int:pk>/crew", dispatch_crew_action, name="dispatching_dispatch_crew_action"),
    path("dispatch/<int:pk>/personnel-search", dispatch_personnel_search, name="dispatching_dispatch_personnel_search"),
    path("dispatch/<int:pk>/expenses", dispatch_expense_action, name="dispatching_dispatch_expense_action"),
    path("dispatch/<int:pk>/reject", dispatch_reject, name="dispatching_dispatch_reject"),
    path("dispatch/<int:pk>/cancel", dispatch_cancel, name="dispatching_dispatch_cancel"),
    path("dispatch/<int:pk>/supersede", dispatch_supersede, name="dispatching_dispatch_supersede"),
    path("dispatch/<int:pk>/attach-reservation", dispatch_attach_reservation, name="dispatching_dispatch_attach_reservation"),

    # ── Asset reservations ──────────────────────────────────────────────
    path("reservations", reservation_index, name="dispatching_reservation_index"),
    path("reservations/create", reservation_create, name="dispatching_reservation_create"),
    path("reservations/asset-search", reservation_asset_search, name="dispatching_reservation_asset_search"),
    path("reservation/<int:pk>", reservation_detail, name="dispatching_reservation_detail"),
    path("reservation/<int:pk>/lifecycle", reservation_lifecycle, name="dispatching_reservation_lifecycle"),
    path("reservation/<int:pk>/user-checkout", reservation_user_checkout, name="dispatching_reservation_user_checkout"),
    path("reservation/<int:pk>/user-checkin", reservation_user_checkin, name="dispatching_reservation_user_checkin"),
    path("reservation/<int:pk>/dispatcher-checkout", reservation_dispatcher_checkout, name="dispatching_reservation_dispatcher_checkout"),
    path("reservation/<int:pk>/dispatcher-checkin", reservation_dispatcher_checkin, name="dispatching_reservation_dispatcher_checkin"),
    path("reservation/<int:pk>/edit", reservation_edit, name="dispatching_reservation_edit"),

    # ── Skills catalogue ────────────────────────────────────────────────
    path("skills", skill_index, name="dispatching_skill_index"),
    path("skills/create", skill_create, name="dispatching_skill_create"),
    path("skills/<int:pk>", skill_detail, name="dispatching_skill_detail"),
    path("skills/<int:pk>/edit", skill_edit, name="dispatching_skill_edit"),
    path("skills/<int:pk>/toggle-active", skill_toggle_active, name="dispatching_skill_toggle_active"),

    # ── Certifications ──────────────────────────────────────────────────
    path("skills/people", skills_linkage_portal, name="dispatching_skills_linkage_portal"),
    path("people/<int:user_id>/skills", user_skills, name="dispatching_user_skills"),
    path("my-certifications", my_certifications, name="dispatching_my_certifications"),
    path("people/<int:user_id>/skills/certify", certification_certify, name="dispatching_certification_certify"),
    path("certifications/<int:pk>/update", certification_update, name="dispatching_certification_update"),
    path("certifications/<int:pk>/revoke", certification_revoke, name="dispatching_certification_revoke"),

    # ── Dispatch templates — lineage ────────────────────────────────────
    path("templates", template_index, name="dispatching_template_index"),
    path("templates/<int:pk>", template_detail, name="dispatching_template_detail"),
    path("templates/<int:pk>/retire", template_retire, name="dispatching_template_retire"),
    path("templates/<int:pk>/reinstate", template_reinstate, name="dispatching_template_reinstate"),

    # ── Dispatch templates — session-backed working draft ──────────────
    path("templates/draft", template_draft_editor, name="dispatching_template_draft_editor"),
    path("templates/draft/start-new", template_draft_start_new, name="dispatching_template_draft_start_new"),
    path("templates/<int:pk>/draft/start-edit", template_draft_start_edit, name="dispatching_template_draft_start_edit"),
    path("templates/<int:pk>/draft/start-copy", template_draft_start_copy, name="dispatching_template_draft_start_copy"),
    path("templates/draft/update", template_draft_update, name="dispatching_template_draft_update"),
    path("templates/draft/commit", template_draft_commit, name="dispatching_template_draft_commit"),

    path("templates/draft/search/materials", material_pool_search, name="dispatching_material_pool_search"),
    path("templates/draft/search/capabilities", capability_pool_search, name="dispatching_capability_pool_search"),
    path("templates/draft/search/configurations", configuration_template_pool_search, name="dispatching_configuration_template_pool_search"),

    # ── Events Portal ──────────────────────────────────────────────────
    path("events", lambda req: _events_portal(req, "dispatching"), name="dispatching_events_portal"),
]

def _events_portal(request, default_type: str):
    from app.events.presentation_layer.entrypoints.events import event_index
    get_copy = request.GET.copy()
    if not get_copy.get("event_type"):
        get_copy["event_type"] = default_type
    request.GET = get_copy
    return event_index(request)
