from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)
from app.detail_extensions.models.provisioning_state import (
    AssetExtensionProvisioningState,
    ModelExtensionProvisioningState,
)

# Concrete extension tables — imported here so Django registers them with this app.
from app.detail_extensions.emissions_info.models import EmissionsInfo
from app.detail_extensions.model_info.models import ModelInfo
from app.detail_extensions.purchase_info.models import PurchaseInfo
from app.detail_extensions.smog_record.models import SmogRecord
from app.detail_extensions.vehicle_registration.models import VehicleRegistration

__all__ = [
    "AssetExtensionProvisioningState",
    "DetailExtensionsByAssetClass",
    "DetailExtensionsByModel",
    "EmissionsInfo",
    "ModelDetailExtensionsByAssetClass",
    "ModelExtensionProvisioningState",
    "ModelInfo",
    "PurchaseInfo",
    "SmogRecord",
    "VehicleRegistration",
]
