"""CapabilityAssignmentValidator — pre-assignment checks for capability operations.

Used by CapabilityManager before creating rows at any layer (class/model/asset).
Raises ValueError with a descriptive message on any violated invariant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.capabilities import (
    AssetCapability,
    AssetClassCapability,
    CapabilityDefinition,
    ModelCapability,
)

if TYPE_CHECKING:
    from app.assets.models import Asset, AssetClass, AssetModel


class CapabilityAssignmentValidator:
    """Validates capability assignments at any layer."""

    @staticmethod
    def check_definition_active(cap_def: CapabilityDefinition) -> None:
        if not cap_def.is_active:
            raise ValueError(
                f"CapabilityDefinition '{cap_def.name}' is inactive and cannot be assigned."
            )

    @staticmethod
    def check_no_duplicate_class(
        asset_class: "AssetClass", cap_def: CapabilityDefinition
    ) -> None:
        if AssetClassCapability.objects.filter(
            asset_class=asset_class, capability_definition=cap_def
        ).exists():
            raise ValueError(
                f"Capability '{cap_def.name}' is already assigned to "
                f"asset class '{asset_class}'."
            )

    @staticmethod
    def check_no_duplicate_model(
        model: "AssetModel", cap_def: CapabilityDefinition
    ) -> None:
        if ModelCapability.objects.filter(
            model=model, capability_definition=cap_def
        ).exists():
            raise ValueError(
                f"Capability '{cap_def.name}' is already assigned to model '{model}'."
            )

    @staticmethod
    def check_no_duplicate_asset(
        asset: "Asset", cap_def: CapabilityDefinition
    ) -> None:
        if AssetCapability.objects.filter(
            asset=asset, capability_definition=cap_def
        ).exists():
            raise ValueError(
                f"Capability '{cap_def.name}' is already assigned to asset '{asset.name}'. "
                f"Remove the existing assignment before re-adding."
            )
