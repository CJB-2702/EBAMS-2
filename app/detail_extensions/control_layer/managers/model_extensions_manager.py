"""ModelExtensionsManager — CRUD + read for a model's extension rows.

Mirror of AssetExtensionsManager for model-target extensions, the ``.extensions``
collaborator on ``ModelDetailExtensionContext`` (P2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.detail_extensions.control_layer.domain_structs.model_extensions_struct import (
    ModelExtensionsStruct,
)
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    ExtensionRegistryValidator,
)
from app.detail_extensions.control_layer.managers.asset_extensions_manager import (
    CardinalityError,
)
from app.detail_extensions.base.extension_descriptor import ExtensionCardinality

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel


class ModelExtensionsManager:
    def __init__(self, model: "AssetModel", actor: "AbstractUser") -> None:
        self.model = model
        self.actor = actor

    def list(self) -> dict:
        return ModelExtensionsStruct(self.model.id).to_dict()

    def get(self, extension_key: str) -> list:
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        return list(descriptor.primary_model.objects.filter(model_id=self.model.id))

    def add(self, extension_key: str, data: dict):
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        model_cls = descriptor.primary_model

        if descriptor.cardinality is ExtensionCardinality.ONE_TO_ONE:
            if model_cls.objects.filter(model_id=self.model.id).exists():
                raise CardinalityError(
                    f"Extension '{extension_key}' is one-to-one; a row already exists "
                    f"for model {self.model.id}."
                )

        with transaction.atomic():
            return model_cls.objects.create(
                model=self.model,
                created_by=self.actor,
                updated_by=self.actor,
                **data,
            )

    def update(self, extension_key: str, row_id: int, data: dict):
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        with transaction.atomic():
            row = descriptor.primary_model.objects.get(id=row_id, model_id=self.model.id)
            for field_name, value in data.items():
                setattr(row, field_name, value)
            row.updated_by = self.actor
            row.save()
            return row

    def remove(self, extension_key: str, row_id: int) -> None:
        descriptor = ExtensionRegistryValidator.resolve(extension_key)
        with transaction.atomic():
            descriptor.primary_model.objects.filter(
                id=row_id, model_id=self.model.id
            ).delete()
