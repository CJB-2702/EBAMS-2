from app.detail_extensions.base.extension_descriptor import (
    DetailExtension,
    ExtensionCardinality,
    ExtensionTarget,
)
from app.detail_extensions.purchase_info.manifest import PURCHASE_INFO_MANIFEST
from app.detail_extensions.purchase_info.models import PurchaseInfo


class PurchaseInfoExtension(DetailExtension):
    key = "purchase_info"
    label = "Purchase Information"
    target = ExtensionTarget.ASSET
    cardinality = ExtensionCardinality.ONE_TO_ONE
    primary_model = PurchaseInfo
    manifest = PURCHASE_INFO_MANIFEST
