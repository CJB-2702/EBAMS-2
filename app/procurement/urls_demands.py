"""Phase 1 — the Demand Loop. Owned exclusively by this wave (build_plan/phase_1_demand_loop.md).

Route names match the contract declared in phase_0_schema_and_shell.md §6.
"""

from django.urls import path

from app.procurement.presentation_layer.entrypoints.demands import (
    demand_create,
    demand_detail,
    demand_edit,
    demand_index,
    demand_queue_for_issuance,
    demand_queue_for_purchasing,
    purchasing_queue_panel,
)

urlpatterns = [
    path("", demand_index, name="demand_index"),
    path("create/", demand_create, name="demand_create"),
    # Bulk action bar on the list above.
    path(
        "queue-for-purchasing/",
        demand_queue_for_purchasing,
        name="demand_queue_for_purchasing",
    ),
    path(
        "queue-for-issuance/",
        demand_queue_for_issuance,
        name="demand_queue_for_issuance",
    ),
    # Reachable from every page in the application (topnav badge), so it is
    # its own route rather than a `format=` on the list.
    path(
        "purchasing-queue/panel/",
        purchasing_queue_panel,
        name="purchasing_queue_panel",
    ),
    path("<int:pk>/", demand_detail, name="demand_detail"),
    path("<int:pk>/edit/", demand_edit, name="demand_edit"),
]
