"""Inventory app URLs.

D84: `shipments/` is a thin duplicate view/edit surface over procurement's
own `Shipment`/`ShipmentLine` rows — no `inventory.Shipment` model exists.
Route shapes mirror `app.procurement.urls_shipments` (list, detail, edit) but
deliberately omit `create`/`receive` — recording a brand-new shipment stays
procurement's job (D83's scope note); Inventory only views and edits
shipments that already exist.

Phase 2 adds the app landing page (`""`) and the stock list
(`active-inventory/`) per `inventory_build_kit/build_plan/02_phase_active_inventory.md`.
"""

from django.urls import path

from app.inventory.presentation_layer.entrypoints.active_inventory import (
    active_inventory_index,
    active_inventory_inline_edit,
)
from app.inventory.presentation_layer.entrypoints.home import inventory_home
from app.inventory.presentation_layer.entrypoints.intake import (
    auto_intake_portal,
    intake_dashboard,
    intake_session_detail,
    scan_intake_start,
)
from app.inventory.presentation_layer.entrypoints.issues import (
    issuance_location_portal,
    issuance_portal,
    issue_detail,
    issue_session_detail,
    issues_index,
    pending_stock_adjustments_index,
)
from app.inventory.presentation_layer.entrypoints.movements import (
    movement_detail,
    movement_portal,
    movements_index,
    putaway_worklist,
)
from app.inventory.presentation_layer.entrypoints.reconciliation import (
    reconciliation_detail,
    reconciliation_hub,
)
from app.inventory.presentation_layer.entrypoints.shipments import (
    inventory_shipment_detail,
    inventory_shipment_edit,
    inventory_shipment_index,
)
from app.inventory.presentation_layer.entrypoints.audits import (
    audit_session_index,
    audit_session_start,
    audit_session_detail,
    audit_log_index,
)
from app.inventory.presentation_layer.entrypoints.topography import (
    room_detail,
    room_layout,
    room_location_detail,
    room_location_layout,
    storage_location_search,
    warehouse_detail,
    warehouse_index,
)

urlpatterns = [
    path("", inventory_home, name="inventory_home"),
    path("active-inventory/", active_inventory_index, name="active_inventory_index"),
    path("active-inventory/<int:pk>/inline-edit/", active_inventory_inline_edit, name="active_inventory_inline_edit"),
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
    # Phase 3 — Warehouse/Room/RoomLocation topography + SVG spatial engine.
    path("warehouses/", warehouse_index, name="inventory_warehouse_index"),
    path("warehouse/<int:pk>/", warehouse_detail, name="inventory_warehouse_detail"),
    path("room/<int:pk>/", room_detail, name="inventory_room_detail"),
    path("room/<int:pk>/layout/", room_layout, name="inventory_room_layout"),
    path(
        "room-location/<int:pk>/",
        room_location_detail,
        name="inventory_room_location_detail",
    ),
    path(
        "room-location/<int:pk>/layout/",
        room_location_layout,
        name="inventory_room_location_layout",
    ),
    path(
        "storage-locations/search/",
        storage_location_search,
        name="storage_location_search",
    ),
    # Phase 4 — Intake Engine Core & Auto Intake Portal.
    path("intake/", intake_dashboard, name="inventory_intake_dashboard"),
    path("intake/auto/", auto_intake_portal, name="inventory_auto_intake_portal"),
    path(
        "intake/session/<int:pk>/",
        intake_session_detail,
        name="inventory_intake_session_detail",
    ),
    # Phase 5 — Scan Sessions & Reconciliation Hub.
    path("intake/scan/", scan_intake_start, name="inventory_scan_intake_start"),
    path(
        "intake/reconciliations/",
        reconciliation_hub,
        name="inventory_reconciliation_hub",
    ),
    path(
        "intake/reconciliation/<int:pk>/",
        reconciliation_detail,
        name="inventory_reconciliation_detail",
    ),
    # Phase 6 — Part Movements, Putaway GUI & Issuance.
    path("movements/create/", movement_portal, name="inventory_movement_portal"),
    path("putaway/", putaway_worklist, name="inventory_putaway_worklist"),
    path("movements/", movements_index, name="inventory_movements_index"),
    path("movement/<int:pk>/", movement_detail, name="inventory_movement_detail"),
    path("issues/create/", issuance_portal, name="inventory_issuance_portal"),
    path("issue-parts/", issuance_portal, name="inventory_issue_parts"),
    path(
        "issues/from-location/",
        issuance_location_portal,
        name="inventory_issuance_location_portal",
    ),
    path("issues/", issues_index, name="inventory_issues_index"),
    path(
        "issues/session/<int:pk>/",
        issue_session_detail,
        name="inventory_issue_session_detail",
    ),
    path("issue/<int:pk>/", issue_detail, name="inventory_issue_detail"),
    path("pending-adjustments/", pending_stock_adjustments_index, name="inventory_pending_adjustments_index"),
    # Phase 7 — Auditing
    path("audits/", audit_session_index, name="inventory_audit_session_index"),
    path("audits/start/", audit_session_start, name="inventory_audit_session_start"),
    path("audit/<int:pk>/", audit_session_detail, name="inventory_audit_session_detail"),
    path("audit-logs/", audit_log_index, name="inventory_audit_log_index"),
]
