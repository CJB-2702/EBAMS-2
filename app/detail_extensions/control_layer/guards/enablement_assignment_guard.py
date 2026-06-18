"""Guard type: Policy + Validator.

``AssignmentPolicy`` — may this actor configure extension enablement?
``AssignmentValidator`` — does this assign/unassign call make structural sense?
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.administration.control_layer.permissions.permission_grant_guard import (
    is_admin_actor,
)
from app.detail_extensions.base.extension_descriptor import ExtensionTarget
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    ExtensionRegistryValidator,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssignmentPermissionDenied(PermissionError):
    """Raised when the actor is not authorised to assign or unassign extensions."""


class AssignmentValidationError(ValueError):
    """Raised when an assign/unassign call is structurally invalid."""


class AssignmentPolicy:
    """Policy: only admins (superuser or ``generic_admin`` group) may configure enablements."""

    @staticmethod
    def assert_may_configure(actor: "AbstractUser") -> None:
        if not is_admin_actor(actor):
            raise AssignmentPermissionDenied(
                "Only admins or superusers may assign or unassign extensions."
            )


class AssignmentValidator:
    """Validates that an assign/unassign call is structurally coherent.

    Checks:
    - extension_key resolves in the registry
    - the requested scope (class vs model) matches the extension's target
    """

    @staticmethod
    def assert_assign_to_class(extension_key: str) -> None:
        """Assert that the extension is an ASSET-target extension (class scope = asset scope)."""
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        if descriptor.target is not ExtensionTarget.ASSET:
            raise AssignmentValidationError(
                f"Extension '{extension_key}' targets models, not asset classes. "
                f"Use assign_to_class only for ASSET-target extensions."
            )

    @staticmethod
    def assert_assign_to_model(extension_key: str) -> None:
        """Assert that the extension is an ASSET-target extension (model-level override scope)."""
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        if descriptor.target is not ExtensionTarget.ASSET:
            raise AssignmentValidationError(
                f"Extension '{extension_key}' targets AssetModel, not individual model overrides. "
                f"Use assign_to_class (ModelDetailExtensionsByAssetClass) for MODEL-target extensions."
            )

    @staticmethod
    def assert_assign_model_ext_to_class(extension_key: str) -> None:
        """Assert that the extension is a MODEL-target extension."""
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        if descriptor.target is not ExtensionTarget.MODEL:
            raise AssignmentValidationError(
                f"Extension '{extension_key}' targets assets, not models. "
                f"Use the asset-class or model scope for ASSET-target extensions."
            )
