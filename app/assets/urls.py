"""Assets sub-application URL routes (UI MOCK — hard-coded data, no persistence).

See assets_ui_plan_kit/route_map.md for the page map.
"""

from django.urls import path

from app.assets.presentation_layer.entrypoints.assets import (
    asset_create,
    asset_detail,
    asset_edit,
    asset_hierarchy_edit,
    asset_images,
    asset_index,
    asset_meter_history,
)
from app.assets.presentation_layer.entrypoints.capabilities import (
    asset_bulk_management,
    asset_capabilities_detail,
    asset_capabilities_edit,
    asset_capability_index,
    capability_definition_create,
    capability_definition_detail,
    capability_definition_edit,
    capability_definition_index,
    capability_index,
    class_capability_index,
    model_capability_index,
)
from app.assets.presentation_layer.entrypoints.classes import (
    class_create,
    class_detail,
    class_edit,
    class_index,
)
from app.assets.presentation_layer.entrypoints.configurations import (
    asset_configuration_detail,
    asset_configuration_edit,
    asset_configuration_index,
    config_template_builder,
    config_template_detail,
    config_template_edit,
    config_template_index,
    config_template_name_search,
    configurations_index,
    defined_modification_create,
    defined_modification_detail,
    defined_modification_edit,
    defined_modification_index,
    modification_applicability_edit,
    modification_applicability_set_mode,
)
from app.assets.presentation_layer.entrypoints.asset_relationships import (
    asset_relationships_index,
    children_attach,
    children_detach,
    children_edit,
    children_expand,
    children_search,
    children_view,
)
from app.assets.presentation_layer.entrypoints.dashboard import asset_dashboard
from app.assets.presentation_layer.entrypoints.manufacturers import (
    manufacturer_create,
    manufacturer_detail,
    manufacturer_edit,
    manufacturer_index,
)
from app.assets.presentation_layer.entrypoints.meter_history import meter_history_index
from app.assets.presentation_layer.entrypoints.models import (
    model_create,
    model_detail,
    model_edit,
    model_index,
    model_move_manufacturers,
)
from app.assets.presentation_layer.entrypoints.model_library import (
    library_add_comment,
    library_add_document,
    library_add_image,
    library_remove_document,
    library_remove_image,
    library_set_primary_image,
    model_library,
)

urlpatterns = [
    # Hub
    path("", asset_dashboard, name="asset_dashboard"),

    # Core — Assets
    path("assets/", asset_index, name="asset_index"),
    path("assets/create/", asset_create, name="asset_create"),
    path("assets/<int:asset_id>/", asset_detail, name="asset_detail"),
    path("assets/<int:asset_id>/edit/", asset_edit, name="asset_edit"),
    path("assets/<int:asset_id>/hierarchy/edit/", asset_hierarchy_edit, name="asset_hierarchy_edit"),
    path("assets/<int:asset_id>/images/", asset_images, name="asset_images"),
    path("assets/<int:asset_id>/meter-history/", asset_meter_history, name="asset_meter_history"),
    path("assets/<int:asset_id>/children/", children_view, name="children_index"),
    path("assets/<int:asset_id>/children/view/", children_view, name="children_view"),
    path("assets/<int:asset_id>/children/edit/", children_edit, name="children_edit"),
    path("assets/<int:asset_id>/children/expand/", children_expand, name="children_expand"),
    path("assets/<int:asset_id>/children/search/", children_search, name="children_search"),
    path("assets/<int:asset_id>/children/attach/", children_attach, name="children_attach"),
    path("assets/<int:asset_id>/children/detach/", children_detach, name="children_detach"),
    path("assets/<int:asset_id>/configuration/", asset_configuration_detail, name="asset_configuration_detail"),
    path("assets/<int:asset_id>/configuration/edit/", asset_configuration_edit, name="asset_configuration_edit"),
    path("assets/<int:asset_id>/capabilities/", asset_capabilities_detail, name="asset_capabilities_detail"),
    path("assets/<int:asset_id>/capabilities/view/", asset_capabilities_detail, name="asset_capabilities_view"),
    path("assets/<int:asset_id>/capabilities/edit/", asset_capabilities_edit, name="asset_capabilities_edit"),
    path("assets/<int:asset_id>/capabilitys/", asset_capabilities_detail, name="asset_capabilitys_detail_redirect"),
    path("assets/<int:asset_id>/capabilitys/view/", asset_capabilities_detail, name="asset_capabilitys_view"),
    path("assets/<int:asset_id>/capabilitys/edit/", asset_capabilities_edit, name="asset_capabilitys_edit"),

    # Core — Models
    path("models/", model_index, name="model_index"),
    path("models/create/", model_create, name="model_create"),
    path("models/<int:model_id>/", model_detail, name="model_detail"),
    path("models/<int:model_id>/edit/", model_edit, name="model_edit"),
    path("models/<int:model_id>/move-manufacturers/", model_move_manufacturers, name="model_move_manufacturers"),
    # Model library — composed view across all versions of a model line, plus its
    # version-scoped write endpoints (keyed by model_id, redirect to the library).
    path("models/<int:model_id>/library/add-document/", library_add_document, name="model_library_add_document"),
    path("models/<int:model_id>/library/remove-document/", library_remove_document, name="model_library_remove_document"),
    path("models/<int:model_id>/library/add-image/", library_add_image, name="model_library_add_image"),
    path("models/<int:model_id>/library/remove-image/", library_remove_image, name="model_library_remove_image"),
    path("models/<int:model_id>/library/set-primary-image/", library_set_primary_image, name="model_library_set_primary_image"),
    path("models/<int:model_id>/library/add-comment/", library_add_comment, name="model_library_add_comment"),
    path("models/<str:model_name>/library/", model_library, name="model_library"),

    # Core — Classes
    path("classes/", class_index, name="class_index"),
    path("classes/create/", class_create, name="class_create"),
    path("classes/<int:class_id>/", class_detail, name="class_detail"),
    path("classes/<int:class_id>/edit/", class_edit, name="class_edit"),

    # Core — Manufacturers
    path("manufacturers/", manufacturer_index, name="manufacturer_index"),
    path("manufacturers/create/", manufacturer_create, name="manufacturer_create"),
    path("manufacturers/<int:manufacturer_id>/", manufacturer_detail, name="manufacturer_detail"),
    path("manufacturers/<int:manufacturer_id>/edit/", manufacturer_edit, name="manufacturer_edit"),

    # Core — Meter History
    path("meter-history/", meter_history_index, name="meter_history_index"),

    # Capabilities
    path("capabilities/", capability_index, name="capability_index"),
    path("capabilities/definitions/", capability_definition_index, name="capability_definition_index"),
    path("capabilities/definitions/create/", capability_definition_create, name="capability_definition_create"),
    path("capabilities/definitions/<int:definition_id>/", capability_definition_detail, name="capability_definition_detail"),
    path("capabilities/definitions/<int:definition_id>/view/", capability_definition_detail, name="capability_definition_view"),
    path("capabilities/definitions/<int:definition_id>//view/", capability_definition_detail, name="capability_definition_view_double_slash"),
    path("capabilities/definitions/<int:definition_id>/edit/", capability_definition_edit, name="capability_definition_edit"),
    path("capabilities/definitions/<int:definition_id>/asset-bulk-managment/", asset_bulk_management, name="asset_bulk_management_typo"),
    path("capabilities/definitions/<int:definition_id>/asset-bulk-management/", asset_bulk_management, name="asset_bulk_management"),
    path("capabilities/by-class/", class_capability_index, name="class_capability_index"),
    path("capabilities/by-model/", model_capability_index, name="model_capability_index"),
    path("capabilities/by-asset/", asset_capability_index, name="asset_capability_index"),

    # Configurations
    path("configurations/", configurations_index, name="configurations_index"),
    path("configurations/templates/", config_template_index, name="config_template_index"),
    path("configurations/templates/builder/", config_template_builder, name="config_template_builder"),
    path("configurations/templates/name-search/", config_template_name_search, name="config_template_name_search"),
    path("configurations/templates/<int:template_id>/", config_template_detail, name="config_template_detail"),
    path("configurations/templates/<int:template_id>/edit/", config_template_edit, name="config_template_edit"),
    path("configurations/modifications/", defined_modification_index, name="defined_modification_index"),
    path("configurations/modifications/create/", defined_modification_create, name="defined_modification_create"),
    path("configurations/modifications/<int:modification_id>/", defined_modification_detail, name="defined_modification_detail"),
    path("configurations/modifications/<int:modification_id>/edit/", defined_modification_edit, name="defined_modification_edit"),
    path("configurations/modifications/<int:modification_id>/applicability/", modification_applicability_edit, name="modification_applicability_edit"),
    path("configurations/modifications/<int:modification_id>/applicability/set-mode/", modification_applicability_set_mode, name="modification_applicability_set_mode"),
    path("configurations/by-asset/", asset_configuration_index, name="asset_configuration_index"),

    # Asset Relationships (parent/child grouping)
    path("asset-relationships/", asset_relationships_index, name="asset_relationships_index"),

    # Asset Events Portal
    path("events/", lambda req: _events_portal(req, "asset_management"), name="asset_events_portal"),
]

def _events_portal(request, default_type: str):
    from app.events.presentation_layer.entrypoints.events import event_index
    get_copy = request.GET.copy()
    if not get_copy.get("event_type"):
        get_copy["event_type"] = default_type
    request.GET = get_copy
    return event_index(request)
