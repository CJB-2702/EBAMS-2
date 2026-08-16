"""Phase 3 — the Receiving Loop. Owned exclusively by this wave
(build_plan/phase_3_receiving_loop.md).

Route names match the contract declared in phase_0_schema_and_shell.md §6 —
they were reserved against a placeholder so waves 1-3 could be built in
parallel, and only the views behind them changed here.

Note what is NOT declared: `shipments/<id>/lines/<line_id>/split`. The splitting
wizard is absorbed entirely into `shipment_edit` as `?line_id=`, because
"assign some of this line to that order line" is one decision, and giving it
its own route made the user pick a verb before they had picked a target.
"""

from django.urls import path

from app.procurement.presentation_layer.entrypoints.shipments import (
    shipment_create,
    shipment_detail,
    shipment_edit,
    shipment_index,
)

urlpatterns = [
    path("", shipment_index, name="shipment_index"),
    path("create/", shipment_create, name="shipment_create"),
    path("<int:pk>/", shipment_detail, name="shipment_detail"),
    path("<int:pk>/edit/", shipment_edit, name="shipment_edit"),
]
