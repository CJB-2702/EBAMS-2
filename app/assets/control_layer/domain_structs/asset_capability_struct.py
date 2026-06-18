"""AssetCapabilityStruct — read model for an asset's capability assignments.

Loads all active AssetCapability rows for an asset with their resolved
CapabilityDefinition, plus the full cascade provenance — which level a
capability originated from: the asset's class template, the model template, or a
manual add. This mirrors the copy-on-create cascade (class → model → asset) so a
reader can answer "why does this asset have/lack capability X?".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.capabilities import (
    AssetCapability,
    AssetClassCapability,
    ModelCapability,
)

if TYPE_CHECKING:
    from app.assets.models import Asset


class AssetCapabilityStruct:
    """Read model for an asset's effective capability set with cascade provenance."""

    # Provenance tiers, most-upstream first. The first tier a capability appears
    # in is its origin (the cascade copies downward, so class wins over model).
    PROVENANCE_CLASS = "class"
    PROVENANCE_MODEL = "model"
    PROVENANCE_MANUAL = "manual"

    def __init__(
        self,
        asset: "Asset",
        capabilities: list[AssetCapability],
        model_capability_ids: set[int],
        class_capability_ids: set[int] | None = None,
    ) -> None:
        self.asset = asset
        self.capabilities = capabilities
        # capability_definition_ids present on the model layer (template provenance).
        self.model_capability_ids = model_capability_ids
        # capability_definition_ids present on the asset-class layer (top of cascade).
        self.class_capability_ids = class_capability_ids or set()

    @classmethod
    def from_asset(
        cls,
        asset: "Asset",
        active_only: bool = True,
    ) -> "AssetCapabilityStruct":
        cap_qs = AssetCapability.objects.filter(asset=asset).select_related(
            "capability_definition"
        )
        if active_only:
            cap_qs = cap_qs.filter(is_active=True)
        capabilities = list(cap_qs.order_by("capability_definition__name"))

        model_cap_ids: set[int] = set(
            ModelCapability.objects.filter(
                model_id=asset.model_id,
                is_active=True,
            ).values_list("capability_definition_id", flat=True)
        )
        class_cap_ids: set[int] = set(
            AssetClassCapability.objects.filter(
                asset_class_id=asset.asset_class_id,
                is_active=True,
            ).values_list("capability_definition_id", flat=True)
        )

        return cls(
            asset=asset,
            capabilities=capabilities,
            model_capability_ids=model_cap_ids,
            class_capability_ids=class_cap_ids,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def is_from_class(self, asset_cap: AssetCapability) -> bool:
        """True if this capability originates at the asset-class template."""
        return asset_cap.capability_definition_id in self.class_capability_ids

    def is_from_model(self, asset_cap: AssetCapability) -> bool:
        """True if this capability is present on the model template."""
        return asset_cap.capability_definition_id in self.model_capability_ids

    def provenance_of(self, asset_cap: AssetCapability) -> str:
        """The cascade level a capability originated from (class > model > manual)."""
        if self.is_from_class(asset_cap):
            return self.PROVENANCE_CLASS
        if self.is_from_model(asset_cap):
            return self.PROVENANCE_MODEL
        return self.PROVENANCE_MANUAL

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset.pk,
            "asset_name": self.asset.name,
            "capabilities": [
                {
                    "id": ac.pk,
                    "capability_definition_id": ac.capability_definition_id,
                    "name": ac.capability_definition.name,
                    "code": ac.capability_definition.code,
                    "is_active": ac.is_active,
                    "qty": ac.qty,
                    "notes": ac.notes,
                    "provenance": self.provenance_of(ac),
                }
                for ac in self.capabilities
            ],
        }
