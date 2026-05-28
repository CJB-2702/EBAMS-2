from app.assets.models.details.asset_class_details import (
    PurchaseInfo,
    SmogRecord,
    VehicleRegistration,
)
from app.assets.models.details.asset_detail_virtual import AssetDetailVirtual
from app.assets.models.details.detail_table_templates import (
    AssetDetailTemplateByAssetClass,
    AssetDetailTemplateByModelType,
    ModelDetailTableTemplate,
)
from app.assets.models.details.model_detail_virtual import ModelDetailVirtual
from app.assets.models.details.model_details import EmissionsInfo, ModelInfo

__all__ = [
    "AssetDetailTemplateByAssetClass",
    "AssetDetailTemplateByModelType",
    "AssetDetailVirtual",
    "EmissionsInfo",
    "ModelDetailTableTemplate",
    "ModelDetailVirtual",
    "ModelInfo",
    "PurchaseInfo",
    "SmogRecord",
    "VehicleRegistration",
]
