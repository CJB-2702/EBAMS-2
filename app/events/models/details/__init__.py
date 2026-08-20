from app.events.models.details.administration import AdministrationDetail
from app.events.models.details.asset_management import AssetManagementDetail
from app.events.models.details.dispatching import (
    DispatchingDetail,
    DispatchScope,
    DispatchWorkflowStatus,
    RejectionCategory,
)
from app.events.models.details.generic import GenericDetail
from app.events.models.details.inventory import InventoryDetail
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.details.system import SystemDetail

__all__ = [
    "AdministrationDetail",
    "AssetManagementDetail",
    "DispatchingDetail",
    "DispatchScope",
    "DispatchWorkflowStatus",
    "GenericDetail",
    "InventoryDetail",
    "MaintenanceDetail",
    "RejectionCategory",
    "SystemDetail",
]
