"""detail_extensions URL routes.

Route order is intentional:
  1. configuration/ routes (literal prefix, no ambiguity)
  2. asset/<id>/ and model/<id>/ (panel — literal owner-type words before catch-all)
  3. <extension-key>/... routes (catch-all via extension_router)

Extension keys 'asset', 'assets', 'model', 'models', 'configuration' are reserved
(validated at startup by ExtensionRegistryValidator) so there is no URL ambiguity.
"""

from django.urls import path

from app.detail_extensions.presentation_layer.entrypoints.aggregate_panel import panel
from app.detail_extensions.presentation_layer.entrypoints.configuration import (
    assign_editor,
    landing,
)
from app.detail_extensions.presentation_layer.entrypoints.extension_router import (
    owner_detail,
    search,
    single_row,
    summary,
)
from app.detail_extensions.presentation_layer.entrypoints.home import (
    home_landing,
    serial_number_templates,
)

urlpatterns = [
    # ── App Home and Custom Placeholders ────────────────────────────────────
    path("", home_landing, name="extension_home"),
    path("serial_number_templates/", serial_number_templates, name="extension_serial_number_templates"),

    # ── Configuration UI ────────────────────────────────────────────────────
    path("configuration/", landing, name="extension_config_landing"),
    path("configuration/<str:extension_key>/", assign_editor, name="extension_assign_editor"),

    # ── Aggregate 360-panel (owner-type literals before catch-all) ──────────
    path("asset/<int:owner_id>/", panel, {"owner_type": "asset"}, name="extension_panel_asset"),
    path("model/<int:owner_id>/", panel, {"owner_type": "model"}, name="extension_panel_model"),

    # ── Per-extension slots (dispatched by extension_router) ─────────────────
    path("<str:extension_key>/", summary, name="extension_summary"),
    path("<str:extension_key>/<str:collection>/", search, name="extension_search"),
    path(
        "<str:extension_key>/<str:owner_type>/<int:owner_id>/",
        owner_detail,
        name="extension_owner_detail",
    ),
    path(
        "<str:extension_key>/<str:owner_type>/<int:owner_id>/<int:row_id>/",
        single_row,
        name="extension_single_row",
    ),
]
