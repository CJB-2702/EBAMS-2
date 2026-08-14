"""Phase 2 — the PO lifecycle. Owned by that wave (build_plan/phase_2_*.md).

Route names match the contract declared in phase_0_schema_and_shell.md §6.
`basic_shipment_manager` is PO-scoped and declared here even though the page
itself belongs to Phase 3.
"""

from django.urls import path

# The Basic Shipment Manager is PO-scoped, so its route lives here — but the
# page belongs to Phase 3 and its view lives with the rest of the shipment
# sector. This import is the seam between the two waves; nothing else in this
# module is Phase 3's.
from app.procurement.presentation_layer.entrypoints.shipments import (
    basic_shipment_manager,
)
from app.procurement.presentation_layer.entrypoints.purchase_orders import (
    purchase_order_create,
    purchase_order_detail,
    purchase_order_edit,
    purchase_order_index,
)

urlpatterns = [
    path("", purchase_order_index, name="purchase_order_index"),
    path("create/", purchase_order_create, name="purchase_order_create"),
    path("<int:pk>/", purchase_order_detail, name="purchase_order_detail"),
    path("<int:pk>/edit/", purchase_order_edit, name="purchase_order_edit"),
    path(
        "<int:pk>/basic-shipment-manager/",
        basic_shipment_manager,
        name="basic_shipment_manager",
    ),
]
