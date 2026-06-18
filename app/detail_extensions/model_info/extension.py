from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionCardinality,
    ExtensionTarget,
)
from app.detail_extensions.model_info.manifest import MODEL_INFO_MANIFEST
from app.detail_extensions.model_info.models import ModelInfo


class ModelInfoExtension(DetailExtension):
    key = "model_info"
    label = "Model Specifications"
    target = ExtensionTarget.MODEL
    cardinality = ExtensionCardinality.ONE_TO_ONE
    primary_model = ModelInfo
    manifest = MODEL_INFO_MANIFEST
