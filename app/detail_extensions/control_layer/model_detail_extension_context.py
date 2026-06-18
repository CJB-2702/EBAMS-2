"""ModelDetailExtensionContext — entry point for a model's extensions.

Mirror of ``AssetDetailExtensionContext`` for model-target extensions. Replaces the
old ``AssetModelContext.plugins`` accessor (P2). Hosts ``ModelExtensionsManager`` as
its ``.extensions`` collaborator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.detail_extensions.control_layer.managers.model_extensions_manager import (
    ModelExtensionsManager,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel


class ModelDetailExtensionContext:
    def __init__(self, model_id: int, actor: "AbstractUser") -> None:
        from app.assets.models import AssetModel

        self.actor = actor
        self.model: "AssetModel" = AssetModel.objects.get(id=model_id)

    @classmethod
    def from_instance(
        cls, model: "AssetModel", actor: "AbstractUser"
    ) -> "ModelDetailExtensionContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.model = model
        return ctx

    @property
    def extensions(self) -> ModelExtensionsManager:
        return ModelExtensionsManager(self.model, self.actor)
