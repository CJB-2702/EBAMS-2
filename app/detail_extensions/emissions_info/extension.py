from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionCardinality,
    ExtensionTarget,
)
from app.detail_extensions.emissions_info.manifest import EMISSIONS_INFO_MANIFEST
from app.detail_extensions.emissions_info.models import EmissionsInfo


class EmissionsInfoExtension(DetailExtension):
    key = "emissions_info"
    label = "Emissions Specifications"
    target = ExtensionTarget.MODEL
    cardinality = ExtensionCardinality.ONE_TO_ONE
    primary_model = EmissionsInfo
    manifest = EMISSIONS_INFO_MANIFEST
