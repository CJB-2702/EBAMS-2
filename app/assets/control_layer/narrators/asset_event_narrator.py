"""AssetEventNarrator — human-readable lifecycle-event strings for assets/models.

Centralizes the title/description text that the old code inlined, so every
lifecycle event reads consistently.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.assets.models import Asset, AssetModel


class AssetEventNarrator:
    @staticmethod
    def asset_created(asset: "Asset") -> tuple[str, str]:
        title = f"Asset Created: {asset.name}"
        description = (
            f"Asset '{asset.name}' (serial {asset.serial_number}) was created."
        )
        return title, description

    @staticmethod
    def model_created(model: "AssetModel") -> tuple[str, str]:
        title = f"Model Created: {model.model_name}"
        description = f"Asset model '{model}' was created."
        return title, description

    @staticmethod
    def asset_fields_changed(asset: "Asset", changes: list[dict]) -> tuple[str, str]:
        title = f"Asset Updated: {asset.name}"
        parts = [
            f"{c['field'].replace('_', ' ').title()} changed from "
            f"'{c['from']}' to '{c['to']}'"
            for c in changes
        ]
        description = "; ".join(parts) if parts else "Asset fields updated."
        return title, description

    # ── P3: configuration events ─────────────────────────────────────────────

    @staticmethod
    def configuration_assigned(asset: "Asset", template_name: str) -> tuple[str, str]:
        title = f"Configuration Assigned: {template_name}"
        description = (
            f"Configuration template '{template_name}' assigned to asset '{asset.name}'."
        )
        return title, description

    @staticmethod
    def modification_added(asset: "Asset", modification_name: str) -> tuple[str, str]:
        title = f"Modification Added: {modification_name}"
        description = (
            f"Modification '{modification_name}' documented on asset '{asset.name}'."
        )
        return title, description

    @staticmethod
    def modification_removed(asset: "Asset", modification_name: str) -> tuple[str, str]:
        title = f"Modification Removed: {modification_name}"
        description = (
            f"Modification '{modification_name}' removed from asset '{asset.name}'."
        )
        return title, description

    # ── Relationship events (parent/child) ──────────────────────────────────

    @staticmethod
    def child_attached(parent: "Asset", child: "Asset") -> tuple[str, str]:
        title = f"Asset Attached: {child.name} under {parent.name}"
        description = (
            f"Asset '{child.name}' (serial {child.serial_number}) was attached as a "
            f"child of '{parent.name}' (serial {parent.serial_number})."
        )
        return title, description

    @staticmethod
    def child_detached(parent: "Asset", child: "Asset") -> tuple[str, str]:
        title = f"Asset Detached: {child.name} from {parent.name}"
        description = (
            f"Asset '{child.name}' (serial {child.serial_number}) was detached from "
            f"'{parent.name}' and is now a standalone root asset."
        )
        return title, description

    # ── P4: capability events ────────────────────────────────────────────────

    @staticmethod
    def capability_added(asset: "Asset", capability_name: str) -> tuple[str, str]:
        title = f"Capability Added: {capability_name}"
        description = (
            f"Capability '{capability_name}' added to asset '{asset.name}'."
        )
        return title, description

    @staticmethod
    def capability_added_from_model(asset: "Asset", capability_name: str) -> tuple[str, str]:
        title = f"Capability Added: {capability_name}"
        description = (
            f"Capability '{capability_name}' auto-assigned to asset '{asset.name}' "
            f"from model template at creation."
        )
        return title, description

    @staticmethod
    def capability_removed(asset: "Asset", capability_name: str) -> tuple[str, str]:
        title = f"Capability Removed: {capability_name}"
        description = (
            f"Capability '{capability_name}' removed from asset '{asset.name}'."
        )
        return title, description
