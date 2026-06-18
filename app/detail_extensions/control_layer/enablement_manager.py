"""EnablementManager — assign/unassign extension enablement rows.

All writes to the three enablement tables go through here.
Entrypoints stay thin: parse via adaptor → call the verb here → redirect/render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.detail_extensions.control_layer.guards.enablement_assignment_guard import (
    AssignmentPolicy,
    AssignmentValidator,
)
from app.detail_extensions.models.enablement import (
    DetailExtensionsByAssetClass,
    DetailExtensionsByModel,
    ModelDetailExtensionsByAssetClass,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class EnablementManager:
    """Domain verbs for toggling extension enablement on classes and models."""

    # ── Asset-target extensions assigned at class scope ───────────────────────

    @staticmethod
    def assign_to_class(
        *,
        extension_key: str,
        asset_class_id: int,
        actor: "AbstractUser",
    ) -> DetailExtensionsByAssetClass:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_to_class(extension_key)
        with transaction.atomic():
            obj, _ = DetailExtensionsByAssetClass.objects.get_or_create(
                asset_class_id=asset_class_id,
                extension_key=extension_key,
                defaults={"created_by": actor, "updated_by": actor},
            )
            return obj

    @staticmethod
    def unassign_from_class(
        *,
        extension_key: str,
        asset_class_id: int,
        actor: "AbstractUser",
    ) -> None:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_to_class(extension_key)
        with transaction.atomic():
            DetailExtensionsByAssetClass.objects.filter(
                asset_class_id=asset_class_id,
                extension_key=extension_key,
            ).delete()

    # ── Asset-target extensions assigned at model scope (per-model override) ──

    @staticmethod
    def assign_to_model(
        *,
        extension_key: str,
        model_id: int,
        actor: "AbstractUser",
    ) -> DetailExtensionsByModel:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_to_model(extension_key)
        with transaction.atomic():
            obj, _ = DetailExtensionsByModel.objects.get_or_create(
                model_id=model_id,
                extension_key=extension_key,
                defaults={"created_by": actor, "updated_by": actor},
            )
            return obj

    @staticmethod
    def unassign_from_model(
        *,
        extension_key: str,
        model_id: int,
        actor: "AbstractUser",
    ) -> None:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_to_model(extension_key)
        with transaction.atomic():
            DetailExtensionsByModel.objects.filter(
                model_id=model_id,
                extension_key=extension_key,
            ).delete()

    # ── Model-target extensions assigned at class scope ───────────────────────

    @staticmethod
    def assign_model_ext_to_class(
        *,
        extension_key: str,
        asset_class_id: int,
        actor: "AbstractUser",
    ) -> ModelDetailExtensionsByAssetClass:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_model_ext_to_class(extension_key)
        with transaction.atomic():
            obj, _ = ModelDetailExtensionsByAssetClass.objects.get_or_create(
                asset_class_id=asset_class_id,
                extension_key=extension_key,
                defaults={"created_by": actor, "updated_by": actor},
            )
            return obj

    @staticmethod
    def unassign_model_ext_from_class(
        *,
        extension_key: str,
        asset_class_id: int,
        actor: "AbstractUser",
    ) -> None:
        AssignmentPolicy.assert_may_configure(actor)
        AssignmentValidator.assert_assign_model_ext_to_class(extension_key)
        with transaction.atomic():
            ModelDetailExtensionsByAssetClass.objects.filter(
                asset_class_id=asset_class_id,
                extension_key=extension_key,
            ).delete()
