"""AssetFactory — stateless creation of an Asset root and its required threads.

Refactor of the old ``asset_handler.py``. Creates the two activity surfaces
(photo gallery + documentation) and the Asset row, copying ``asset_class`` from
the model (the deliberate denormalization). **No commit of its own** — it runs
inside ``AssetCreationOrchestrator``'s transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.control_layer.guards.asset_serial_number_guard import (
    AssetSerialNumberValidator,
)
from app.assets.models import Asset, AssetModel
from app.events.models import ActivityThread, FileSet

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class AssetFactory:
    REQUIRED = ("name", "serial_number", "domain_id", "model_id")

    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> Asset:
        errors = cls._validate(data)
        if errors:
            raise AssetValidationError(errors)

        # asset_class is denormalized from the model — never trust caller input.
        model = AssetModel.objects.get(id=data["model_id"])

        photo_gallery = FileSet.objects.create(
            domain_id=data["domain_id"],
            created_by=actor,
            updated_by=actor,
        )
        documentation = ActivityThread.objects.create(
            domain_id=data["domain_id"],
            created_by=actor,
            updated_by=actor,
        )

        parent_id = data.get("parent_asset_id")
        parent = Asset.objects.get(id=parent_id) if parent_id else None
        if parent is not None:
            root_id = parent.root_asset_id or parent.id
            depth = (parent.depth_from_root or 0) + 1
        else:
            root_id = None
            depth = 0

        asset = Asset.objects.create(
            name=data["name"],
            serial_number=data["serial_number"].strip(),
            domain_id=data["domain_id"],
            model_id=model.id,
            asset_class_id=model.asset_class_id,
            photo_gallery=photo_gallery,
            documentation=documentation,
            status=data.get("status", "Active"),
            parent_asset=parent,
            root_asset_id=root_id,
            depth_from_root=depth,
            created_by=actor,
            updated_by=actor,
        )
        # Self-rooted when it has no parent.
        if root_id is None:
            asset.root_asset_id = asset.id
            asset.save(update_fields=["root_asset"])
        return asset

    @classmethod
    def _validate(cls, data: dict) -> list[str]:
        errors: list[str] = []
        for required in cls.REQUIRED:
            if not data.get(required):
                errors.append(f"{required} is required.")
        if data.get("serial_number"):
            errors.extend(AssetSerialNumberValidator.validate(data["serial_number"]))
        return errors
