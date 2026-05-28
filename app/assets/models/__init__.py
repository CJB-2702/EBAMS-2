from app.assets.models.asset_parent_history import AssetParentHistory
from app.assets.models.capabilities import (
    AssetCapability,
    AssetClassCapability,
    CapabilityDefinition,
    ModelCapability,
)
from app.assets.models.configurations import (
    ActualModification,
    AssetConfiguration,
    ConfigurationTemplate,
    DefinedModification,
    TemplateChild,
    TemplateModification,
)
from app.assets.models.core import (
    Asset,
    AssetClass,
    AssetImage,
    AssetModel,
    Manufacturer,
    MeterHistory,
)
from app.assets.models.details import (
    AssetDetailTemplateByAssetClass,
    AssetDetailTemplateByModelType,
    AssetDetailVirtual,
    EmissionsInfo,
    ModelDetailTableTemplate,
    ModelDetailVirtual,
    ModelInfo,
    PurchaseInfo,
    SmogRecord,
    VehicleRegistration,
)
from app.assets.models.domain_junctions import (
    AssetClassDomain,
    ModelDomain,
    ModelManufacturer,
)

__all__ = [
    "ActualModification",
    "Asset",
    "AssetCapability",
    "AssetClass",
    "AssetClassCapability",
    "AssetClassDomain",
    "AssetConfiguration",
    "AssetDetailTemplateByAssetClass",
    "AssetDetailTemplateByModelType",
    "AssetDetailVirtual",
    "AssetImage",
    "AssetModel",
    "AssetParentHistory",
    "CapabilityDefinition",
    "ConfigurationTemplate",
    "DefinedModification",
    "EmissionsInfo",
    "Manufacturer",
    "MeterHistory",
    "ModelCapability",
    "ModelDetailTableTemplate",
    "ModelDetailVirtual",
    "ModelDomain",
    "ModelInfo",
    "ModelManufacturer",
    "PurchaseInfo",
    "SmogRecord",
    "TemplateChild",
    "TemplateModification",
    "VehicleRegistration",
]
