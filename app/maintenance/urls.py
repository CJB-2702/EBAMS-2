"""URL conf for the maintenance app.

One canonical URL per resource; density and HTMX fragments ride on `format=`
rather than parallel routes (harness/UX_UI.md). The legacy app's six portal
blueprints collapse here into a single flat namespace — the portals were roles,
not resources, and the merged hub replaces them.
"""

from __future__ import annotations

from django.urls import path

from app.maintenance.presentation_layer.entrypoints.action_views import (
    action_create,
    action_reorder,
    action_update,
)
from app.maintenance.presentation_layer.entrypoints.create_assign_views import (
    create_assign,
    unassigned_events,
)
from app.maintenance.presentation_layer.entrypoints.event_views import (
    maintenance_detail,
    maintenance_index,
)
from app.maintenance.presentation_layer.entrypoints.hub_views import maintenance_hub
from app.maintenance.presentation_layer.entrypoints.part_demand_views import (
    part_demand_detail,
    part_demand_index,
)
from app.maintenance.presentation_layer.entrypoints.planning_views import (
    plan_create,
    plan_detail,
    plan_edit,
    plan_index,
    plan_worklist,
    plan_move_asset_models,
)
from app.maintenance.presentation_layer.entrypoints.proto_views import (
    proto_create,
    proto_detail,
    proto_index,
)
from app.maintenance.presentation_layer.entrypoints.technician_views import (
    technician_dashboard,
)
from app.maintenance.presentation_layer.entrypoints.template_views import (
    template_builder,
    template_builder_commit,
    template_builder_update,
    template_detail,
    template_index,
    template_move_asset_models,
    template_toggle_active,
)
from app.maintenance.presentation_layer.entrypoints.work_views import (
    maintenance_assign,
    maintenance_edit,
    maintenance_work,
)
from app.maintenance.presentation_layer.entrypoints.asset_dashboard_views import (
    asset_dashboard,
)

urlpatterns = [
    # The merged hub — replaces the legacy role chooser plus the manager,
    # technician, and fleet dashboards.
    path("", maintenance_hub, name="maintenance_hub"),
    path("technician-dashboard", technician_dashboard, name="technician_dashboard"),
    path("assets-dashboard", asset_dashboard, name="maintenance_asset_dashboard"),

    # Events (collection + single resource)
    path("events", maintenance_index, name="maintenance_index"),
    path("event/<int:pk>", maintenance_detail, name="maintenance_detail"),

    # The three per-event portals
    path("event/<int:pk>/work", maintenance_work, name="maintenance_work"),
    path("event/<int:pk>/edit", maintenance_edit, name="maintenance_edit"),
    path("event/<int:pk>/assign", maintenance_assign, name="maintenance_assign"),

    # Create & assign
    path("create-assign", create_assign, name="create_assign"),
    path("create", create_assign, name="maintenance_create"),
    path("unassigned", unassigned_events, name="unassigned_events"),

    # Actions (child collection of one event; single-action ops by their own id)
    path("event/<int:maintenance_id>/actions", action_create, name="action_create"),
    path("action/<int:action_id>", action_update, name="action_update"),
    path("action/<int:action_id>/reorder", action_reorder, name="action_reorder"),

    # Maintenance-facing part demand queue (reads procurement.PartDemand
    # outward through MaintenanceDemandLink; every write goes through
    # procurement's PartDemandContext)
    path("part-demands", part_demand_index, name="part_demand_index"),
    path("part-demand/<int:pk>", part_demand_detail, name="part_demand_detail"),

    # Procedure template library
    path("templates", template_index, name="template_index"),
    path("template/<int:pk>", template_detail, name="template_detail"),
    path("template/<int:pk>/toggle-active", template_toggle_active, name="template_toggle_active"),
    path("template/<int:pk>/move-models", template_move_asset_models, name="template_move_asset_models"),

    # Session-backed template builder wizard (multi_step_flows.md)
    path("templates/builder", template_builder, name="template_builder"),
    path("templates/builder/update", template_builder_update, name="template_builder_update"),
    path("templates/builder/commit", template_builder_commit, name="template_builder_commit"),

    # Proto action library
    path("proto-actions", proto_index, name="proto_index"),
    path("proto-actions/create", proto_create, name="proto_create"),
    path("proto-action/<int:pk>", proto_detail, name="proto_detail"),

    # Recurring maintenance plans
    path("plans", plan_index, name="plan_index"),
    path("plans/create", plan_create, name="plan_create"),
    path("plan/<int:pk>", plan_detail, name="plan_detail"),
    path("plan/<int:pk>/edit", plan_edit, name="plan_edit"),
    path("plan/<int:pk>/worklist", plan_worklist, name="plan_worklist"),
    path("plan/<int:pk>/move-models", plan_move_asset_models, name="plan_move_asset_models"),
    path("events-portal", lambda req: _events_portal(req, "maintenance"), name="maintenance_events_portal"),
]

def _events_portal(request, default_type: str):
    from app.events.presentation_layer.entrypoints.events import event_index
    get_copy = request.GET.copy()
    if not get_copy.get("event_type"):
        get_copy["event_type"] = default_type
    request.GET = get_copy
    return event_index(request)
