"""ConfigurationAssignmentValidator — pre-assign checks for configuration templates.

Called by ConfigurationManager.assign() before creating an AssetConfiguration.
Raises ValueError with a descriptive message on any violated invariant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.assets.models import Asset, ConfigurationTemplate


class ConfigurationAssignmentValidator:
    """Validates that a ConfigurationTemplate may be assigned to an Asset."""

    @staticmethod
    def check(asset: "Asset", template: "ConfigurationTemplate") -> None:
        """Raise ValueError if the assignment is not valid."""
        if not template.is_active:
            raise ValueError(
                f"ConfigurationTemplate '{template.name}' is inactive and cannot be assigned."
            )
        if template.model_id != asset.model_id:
            raise ValueError(
                f"Template model mismatch: template '{template.name}' belongs to "
                f"model {template.model_id} but asset '{asset.name}' uses "
                f"model {asset.model_id}."
            )
