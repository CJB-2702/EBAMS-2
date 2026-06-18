"""AssetExtensionsManager — CRUD + read for an asset's extension rows.

The ``.extensions`` collaborator on ``AssetDetailExtensionContext`` (P2). Resolves
extension keys via the registry and enforces cardinality from the descriptor (D5):
ONE_TO_ONE rejects a second row; ONE_TO_MANY appends.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.detail_extensions.control_layer.domain_structs.asset_extensions_struct import (
    AssetExtensionsStruct,
)
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    ExtensionRegistryValidator,
)
from app.detail_extensions.base.extension_descriptor import ExtensionCardinality

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset


class CardinalityError(Exception):
    """Raised when an add() would violate a ONE_TO_ONE extension's single-row rule."""


class AssetExtensionsManager:
    def __init__(self, asset: "Asset", actor: "AbstractUser") -> None:
        self.asset = asset
        self.actor = actor

    def list(self) -> dict:
        return AssetExtensionsStruct(self.asset.id).to_dict()

    def get(self, extension_key: str) -> list:
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        return list(descriptor.primary_model.objects.filter(asset_id=self.asset.id))

    def add(self, extension_key: str, data: dict):
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        model = descriptor.primary_model

        if descriptor.cardinality is ExtensionCardinality.ONE_TO_ONE:
            if model.objects.filter(asset_id=self.asset.id).exists():
                raise CardinalityError(
                    f"Extension '{extension_key}' is one-to-one; a row already exists "
                    f"for asset {self.asset.id}."
                )

        with transaction.atomic():
            return model.objects.create(
                asset=self.asset,
                created_by=self.actor,
                updated_by=self.actor,
                **data,
            )

    def update(self, extension_key: str, row_id: int, data: dict):
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        with transaction.atomic():
            row = descriptor.primary_model.objects.get(id=row_id, asset_id=self.asset.id)
            for field_name, value in data.items():
                setattr(row, field_name, value)
            row.updated_by = self.actor
            row.save()
            return row

    def remove(self, extension_key: str, row_id: int) -> None:
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        with transaction.atomic():
            descriptor.primary_model.objects.filter(
                id=row_id, asset_id=self.asset.id
            ).delete()
