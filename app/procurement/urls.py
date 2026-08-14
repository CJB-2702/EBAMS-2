"""Parent URL conf for the procurement app (Phase 0 §6).

A shared parent including each wave's own url module plus the `/procurement`
hub page and the graph-visualizer placeholder (route declared here, page
built in Phase 4). Each wave edits only its own module
(urls_demands.py / urls_purchase_orders.py / urls_shipments.py).
"""

from __future__ import annotations

from django.urls import include, path

from app.procurement.presentation_layer.entrypoints.shell import (
    not_built_yet,
    procurement_hub,
)
from app.procurement.presentation_layer.entrypoints.vendors import (
    vendor_create,
    vendor_index,
)

urlpatterns = [
    path("", procurement_hub, name="procurement_hub"),
    path("demands/", include("app.procurement.urls_demands")),
    path("purchase-orders/", include("app.procurement.urls_purchase_orders")),
    path("shipments/", include("app.procurement.urls_shipments")),
    path("vendors/", vendor_index, name="vendor_index"),
    path("vendors/create/", vendor_create, name="vendor_create"),
    path("prices/", include("app.procurement.urls_prices")),
    path(
        "graph-association-visualizer/",
        not_built_yet,
        name="procurement_graph_visualizer",
    ),
]
