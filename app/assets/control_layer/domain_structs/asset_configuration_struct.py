"""AssetConfigurationStruct — read model for an asset's full configuration state.

Loads the asset's current configuration (most recent AssetConfiguration),
its resolved template, all active actual modifications, direct child assets,
and the full configuration history (every prior assignment, newest-first, since
"latest wins" leaves earlier rows in place).  Provides expected-vs-actual
progress metrics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.configurations import ActualModification, AssetConfiguration
from app.assets.control_layer.domain_structs.configuration_template_struct import (
    ConfigurationTemplateStruct,
)

if TYPE_CHECKING:
    from app.assets.models import Asset


class AssetConfigurationStruct:
    """Read model combining the asset's configuration with expected/actual data."""

    def __init__(
        self,
        asset: "Asset",
        asset_configuration: AssetConfiguration | None,
        template_struct: ConfigurationTemplateStruct | None,
        actual_modifications: list[ActualModification],
        child_assets: list["Asset"],
        history: list[AssetConfiguration] | None = None,
    ) -> None:
        self.asset = asset
        self.asset_configuration = asset_configuration
        self.template_struct = template_struct
        self.actual_modifications = actual_modifications
        self.child_assets = child_assets
        # Every configuration ever assigned, newest-first (index 0 == current).
        self.history = history or []

    @classmethod
    def from_asset(
        cls,
        asset: "Asset",
        active_modifications_only: bool = True,
    ) -> "AssetConfigurationStruct":
        from app.assets.models import Asset

        # Full assignment history, newest-first; the head is the current config.
        history = list(
            AssetConfiguration.objects.filter(asset=asset)
            .select_related("template")
            .order_by("-created_at")
        )
        asset_config = history[0] if history else None

        template_struct = None
        if asset_config:
            template_struct = ConfigurationTemplateStruct.from_template(asset_config.template)

        mod_qs = ActualModification.objects.filter(asset=asset).select_related(
            "defined_modification"
        )
        if active_modifications_only:
            mod_qs = mod_qs.filter(is_active=True)
        actual_mods = list(mod_qs.order_by("-created_at"))

        child_assets = list(
            Asset.objects.filter(parent_asset=asset).order_by("name")
        )

        return cls(
            asset=asset,
            asset_configuration=asset_config,
            template_struct=template_struct,
            actual_modifications=actual_mods,
            child_assets=child_assets,
            history=history,
        )

    # ── Progress metrics ─────────────────────────────────────────────────────

    def get_modification_progress(self) -> dict:
        """Expected vs documented modification counts."""
        expected_ids: set[int] = set()
        if self.template_struct:
            expected_ids = {
                m.defined_modification_id for m in self.template_struct.modifications
            }
        documented_ids = {am.defined_modification_id for am in self.actual_modifications}
        matched = len(documented_ids & expected_ids)
        extra = len(documented_ids - expected_ids)
        return {
            "documented": len(self.actual_modifications),
            "expected": len(expected_ids),
            "matched": matched,
            "extra": extra,
        }

    def get_child_progress(self) -> dict:
        """Expected vs linked child asset counts."""
        expected = (
            sum(c.quantity for c in self.template_struct.children)
            if self.template_struct
            else 0
        )
        return {"linked": len(self.child_assets), "expected": expected}

    def get_undocumented_modifications(self) -> list:
        """Template modifications not yet present in active actuals."""
        if not self.template_struct:
            return []
        documented_ids = {am.defined_modification_id for am in self.actual_modifications}
        return [
            m
            for m in self.template_struct.modifications
            if m.defined_modification_id not in documented_ids
        ]

    def get_unmatched_children(self) -> list:
        """Expected child model declarations that have no matching child asset."""
        if not self.template_struct:
            return []
        linked_model_ids = {c.model_id for c in self.child_assets}
        return [
            c
            for c in self.template_struct.children
            if c.child_model_id not in linked_model_ids
        ]

    # ── History ──────────────────────────────────────────────────────────────

    def get_history(self) -> list[AssetConfiguration]:
        """Prior configurations only (current excluded), newest-first."""
        return self.history[1:] if len(self.history) > 1 else []

    @staticmethod
    def _config_summary(config: AssetConfiguration) -> dict:
        return {
            "id": config.pk,
            "template_id": config.template_id,
            "template_name": config.template.name if config.template_id else None,
            "verification_status": config.verification_status,
            "is_current": config.is_current,
            "documented_at": config.documented_at,
            "created_at": config.created_at,
        }

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        mod_progress = self.get_modification_progress()
        child_progress = self.get_child_progress()
        return {
            "asset_id": self.asset.pk,
            "asset_name": self.asset.name,
            "has_configuration": self.asset_configuration is not None,
            "verification_status": (
                self.asset_configuration.verification_status
                if self.asset_configuration
                else None
            ),
            "template": self.template_struct.to_dict() if self.template_struct else None,
            "modification_progress": mod_progress,
            "child_progress": child_progress,
            "history_count": len(self.history),
            "history": [self._config_summary(c) for c in self.get_history()],
        }
