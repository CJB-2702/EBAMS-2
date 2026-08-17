"""URL conf for the maintenance app (Step 4)."""

from __future__ import annotations

from django.urls import path

from app.maintenance.presentation_layer.entrypoints.action_views import (
    action_create,
    action_reorder,
    action_update,
)
from app.maintenance.presentation_layer.entrypoints.event_views import (
    maintenance_create,
    maintenance_detail,
    maintenance_index,
)
from app.maintenance.presentation_layer.entrypoints.planning_views import (
    plan_create,
    plan_detail,
    plan_index,
)
from app.maintenance.presentation_layer.entrypoints.proto_views import (
    proto_create,
    proto_index,
)
from app.maintenance.presentation_layer.entrypoints.template_views import (
    template_builder,
    template_builder_commit,
    template_builder_update,
    template_detail,
    template_index,
)

urlpatterns = [
    # Events (collection + single resource)
    path("events", maintenance_index, name="maintenance_index"),
    path("events/create", maintenance_create, name="maintenance_create"),
    path("event/<int:pk>", maintenance_detail, name="maintenance_detail"),

    # Actions (child collection of one event; single-action ops by their own id)
    path("event/<int:maintenance_id>/actions", action_create, name="action_create"),
    path("action/<int:action_id>", action_update, name="action_update"),
    path("action/<int:action_id>/reorder", action_reorder, name="action_reorder"),

    # Procedure template library
    path("templates", template_index, name="template_index"),
    path("template/<int:pk>", template_detail, name="template_detail"),

    # Session-backed template builder wizard (multi_step_flows.md)
    path("templates/builder", template_builder, name="template_builder"),
    path("templates/builder/update", template_builder_update, name="template_builder_update"),
    path("templates/builder/commit", template_builder_commit, name="template_builder_commit"),

    # Proto action library
    path("proto-actions", proto_index, name="proto_index"),
    path("proto-actions/create", proto_create, name="proto_create"),

    # Recurring maintenance plans
    path("plans", plan_index, name="plan_index"),
    path("plans/create", plan_create, name="plan_create"),
    path("plan/<int:pk>", plan_detail, name="plan_detail"),
]
