"""AssetModelContext — entry point for control logic around one model id."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.domain_structs.asset_model_struct import AssetModelStruct
from app.assets.control_layer.handlers.model_asset_class_propagation_handler import (
    ModelAssetClassPropagationHandler,
)
from app.assets.models import ModelCapability, ModelManufacturer

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel

_METADATA_FIELDS = (
    "model_name",
    "subtype_name",
    "revision",
    "meter1_unit",
    "meter2_unit",
    "meter3_unit",
    "meter4_unit",
)
_NULLABLE_FIELDS = frozenset(_METADATA_FIELDS) - {"model_name"}


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

    def update(self, *, data: dict) -> "AssetModel":
        """Apply identity/meter metadata, asset-class change (with propagation),
        and reconcile the linked manufacturer set."""
        m = self.model
        with transaction.atomic():
            changed: list[str] = []
            for field in _METADATA_FIELDS:
                if field in data:
                    value = data[field]
                    if field == "model_name":
                        value = (value or "").strip()
                    elif field in _NULLABLE_FIELDS:
                        value = (value or None)
                    setattr(m, field, value)
                    changed.append(field)
            if changed:
                m.updated_by = self.actor
                m.save(update_fields=[*changed, "updated_at", "updated_by"])

            new_class_id = data.get("asset_class_id")
            if new_class_id is not None and new_class_id != m.asset_class_id:
                self.set_asset_class(new_class_id)

            if "manufacturer_ids" in data:
                self._sync_manufacturers(
                    desired_ids=list(data["manufacturer_ids"]),
                    primary_id=data.get("primary_manufacturer_id"),
                )
        return m

    def set_capabilities(self, *, capability_ids: list[int]) -> None:
        """Reconcile declared model capabilities to the desired definition set."""
        desired = set(capability_ids)
        with transaction.atomic():
            existing = dict(
                ModelCapability.objects.filter(model=self.model).values_list(
                    "capability_definition_id", "id"
                )
            )
            for def_id in desired - existing.keys():
                ModelCapability.objects.create(
                    model=self.model,
                    capability_definition_id=def_id,
                    is_active=True,
                    created_by=self.actor,
                    updated_by=self.actor,
                )
            to_remove = [rid for did, rid in existing.items() if did not in desired]
            if to_remove:
                ModelCapability.objects.filter(id__in=to_remove).delete()

    # ── Internals ────────────────────────────────────────────────────────────
    def _sync_manufacturers(self, *, desired_ids: list[int], primary_id) -> None:
        desired = set(desired_ids)
        existing = dict(
            ModelManufacturer.objects.filter(model=self.model).values_list(
                "manufacturer_id", "id"
            )
        )
        for manufacturer_id in desired - existing.keys():
            ModelManufacturer.objects.create(
                model=self.model,
                manufacturer_id=manufacturer_id,
                is_primary=False,
                created_by=self.actor,
                updated_by=self.actor,
            )
        to_remove = [rid for mid, rid in existing.items() if mid not in desired]
        if to_remove:
            ModelManufacturer.objects.filter(id__in=to_remove).delete()

        # Guarantee exactly one primary among the remaining links.
        links = list(ModelManufacturer.objects.filter(model=self.model))
        if not links:
            return
        chosen = next(
            (lnk for lnk in links if lnk.manufacturer_id == primary_id), links[0]
        )
        for lnk in links:
            should_be = lnk.id == chosen.id
            if lnk.is_primary != should_be:
                lnk.is_primary = should_be
                lnk.updated_by = self.actor
                lnk.save(update_fields=["is_primary", "updated_at", "updated_by"])
