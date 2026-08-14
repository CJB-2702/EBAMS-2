"""Phase 1 — the Demand Loop. Owned exclusively by this wave (build_plan/phase_1_demand_loop.md).

Route names match the contract declared in phase_0_schema_and_shell.md §6.
"""

from django.urls import path

from app.procurement.presentation_layer.entrypoints.demands import (
    demand_create,
    demand_detail,
    demand_edit,
    demand_index,
)

urlpatterns = [
    path("", demand_index, name="demand_index"),
    path("create/", demand_create, name="demand_create"),
    path("<int:pk>/", demand_detail, name="demand_detail"),
    path("<int:pk>/edit/", demand_edit, name="demand_edit"),
]
