"""Inventory app URLs.

D84: `shipments/` is a thin duplicate view/edit surface over procurement's
own `Shipment`/`ShipmentLine` rows — no `inventory.Shipment` model exists.
Route shapes mirror `app.procurement.urls_shipments` (list, detail, edit) but
deliberately omit `create`/`receive` — recording a brand-new shipment stays
procurement's job (D83's scope note); Inventory only views and edits
shipments that already exist.
"""

from django.urls import path

from app.inventory.presentation_layer.entrypoints.shipments import (
    inventory_shipment_detail,
    inventory_shipment_edit,
    inventory_shipment_index,
)

urlpatterns = [
    path("shipments/", inventory_shipment_index, name="inventory_shipment_index"),
    path(
        "shipments/<int:pk>/",
        inventory_shipment_detail,
        name="inventory_shipment_detail",
    ),
    path(
        "shipments/<int:pk>/edit/",
        inventory_shipment_edit,
        name="inventory_shipment_edit",
    ),
]
