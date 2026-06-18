"""OwnerEnablementStruct — the single answer to "which extensions apply here?".

Clusters the enablement rows that bear on one owner (an Asset or an AssetModel)
into the set of ``extension_key``s switched on for it. It is the one place that
resolves enablement, so the provisioner (what to create) and the router (what to
allow) ask the same question and get the same answer.

Resolution rules (mirrors the enablement tables):
  * asset owner → union of class-level and model-level **asset** extensions
        DetailExtensionsByAssetClass[asset.asset_class] ∪ DetailExtensionsByModel[asset.model]
  * model owner → class-level **model** extensions
        ModelDetailExtensionsByAssetClass[model.asset_class]

Read-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.detail_extensions.base.extension_descriptor import ExtensionTarget
from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)

if TYPE_CHECKING:
    from app.assets.models import Asset, AssetModel


class OwnerEnablementStruct:
    """Resolved set of enabled extension keys for one owner."""

    def __init__(self, *, target: ExtensionTarget, owner_id: int, enabled_keys: set[str]) -> None:
        self.target = target
        self.owner_id = owner_id
        self.enabled_keys = enabled_keys

    # ── Builders ─────────────────────────────────────────────────────────────

    @classmethod
    def for_asset(cls, asset: "Asset") -> "OwnerEnablementStruct":
        by_class = DetailExtensionsByAssetClass.objects.filter(
            asset_class_id=asset.asset_class_id
        ).values_list("extension_key", flat=True)
        by_model = DetailExtensionsByModel.objects.filter(
            model_id=asset.model_id
        ).values_list("extension_key", flat=True)
        return cls(
            target=ExtensionTarget.ASSET,
            owner_id=asset.id,
            enabled_keys=set(by_class) | set(by_model),
        )

    @classmethod
    def for_model(cls, model: "AssetModel") -> "OwnerEnablementStruct":
        keys = ModelDetailExtensionsByAssetClass.objects.filter(
            asset_class_id=model.asset_class_id
        ).values_list("extension_key", flat=True)
        return cls(
            target=ExtensionTarget.MODEL,
            owner_id=model.id,
            enabled_keys=set(keys),
        )

    @classmethod
    def for_owner_id(
        cls, *, target: ExtensionTarget, owner_id: int
    ) -> "OwnerEnablementStruct | None":
        """Resolve by target + id; returns None if the owner row is gone."""
        from app.assets.models import Asset, AssetModel

        if target is ExtensionTarget.ASSET:
            asset = Asset.objects.filter(id=owner_id).first()
            return cls.for_asset(asset) if asset is not None else None
        model = AssetModel.objects.filter(id=owner_id).first()
        return cls.for_model(model) if model is not None else None

    # ── Queries ──────────────────────────────────────────────────────────────

    def is_enabled(self, extension_key: str) -> bool:
        return extension_key in self.enabled_keys

    def sorted_keys(self) -> list[str]:
        return sorted(self.enabled_keys)

    def to_dict(self) -> dict:
        return {
            "target": self.target.value,
            "owner_id": self.owner_id,
            "enabled_keys": self.sorted_keys(),
        }
