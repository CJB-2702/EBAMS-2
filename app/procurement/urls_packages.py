"""Phase 3 — the Receiving Loop. Owned exclusively by this wave
(build_plan/phase_3_receiving_loop.md).

Route names match the contract declared in phase_0_schema_and_shell.md §6 —
they were reserved against a placeholder so waves 1-3 could be built in
parallel, and only the views behind them changed here.

Note what is NOT declared: `packages/<id>/lines/<line_id>/split`. The splitting
wizard is absorbed entirely into `package_edit` as `?line_id=`, because
"assign some of this line to that order line" is one decision, and giving it
its own route made the user pick a verb before they had picked a target.
"""

from django.urls import path

from app.procurement.presentation_layer.entrypoints.packages import (
    package_create,
    package_detail,
    package_edit,
    package_index,
    package_receive,
)

urlpatterns = [
    path("", package_index, name="package_index"),
    path("create/", package_create, name="package_create"),
    # The PO-less reactive entry point (D71/D73): a box arrived, the paperwork
    # has not.
    path("receive/", package_receive, name="package_receive"),
    path("<int:pk>/", package_detail, name="package_detail"),
    path("<int:pk>/edit/", package_edit, name="package_edit"),
]
