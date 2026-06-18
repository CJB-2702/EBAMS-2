"""AssetModelContext — entry point for control logic around one model id."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.control_layer.domain_structs.asset_model_struct import AssetModelStruct
from app.assets.control_layer.handlers.model_asset_class_propagation_handler import (
    ModelAssetClassPropagationHandler,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetModelContext:
    def __init__(self, model_id: int, actor: "AbstractUser", *, eager: bool = False) -> None:
        self.actor = actor
        self.struct = AssetModelStruct(model_id, eager=eager)
        self.model = self.struct.model

    @classmethod
    def from_struct(
        cls, struct: AssetModelStruct, actor: "AbstractUser"
    ) -> "AssetModelContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        ctx.model = struct.model
        return ctx

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def set_asset_class(self, asset_class_id: int) -> int:
        """Change the model's class and propagate to its assets. Returns count."""
        return ModelAssetClassPropagationHandler.run(
            model=self.model,
            new_asset_class_id=asset_class_id,
            actor=self.actor,
        )
