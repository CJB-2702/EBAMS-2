"""AssetModelContext — entry point for control logic around one model id."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.domain_structs.asset_model_struct import AssetModelStruct
from app.assets.control_layer.handlers.model_asset_class_propagation_handler import (
    ModelAssetClassPropagationHandler,
)
from app.assets.control_layer.thread_domain import default_domain_id_for
from app.assets.models import ModelCapability, ModelManufacturer
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.events.control_layer.managers.gallery_manager import GalleryManager
from app.events.models import ActivityThread, FileSet

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetModel

_METADATA_FIELDS = (
    "model_name",
    "version",
    "version_rank",
    "config_baselines",
)


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

    # ── Activity surfaces ─────────────────────────────────────────────────────
    @property
    def documents(self) -> ActivityThreadManager:
        return ActivityThreadManager(
            self.model,
            self.actor,
            thread_attr="documentation",
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        )

    @property
    def images(self) -> GalleryManager:
        # A model line spans domains, so its gallery FileSet is created lazily with
        # a bootstrap domain on first upload.
        return GalleryManager(
            self.model,
            self.actor,
            gallery_attr="photo_gallery",
            gallery_thread_cls=FileSet,
            domain_id_resolver=lambda: default_domain_id_for(FileSet),
        )

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def set_asset_class(self, asset_class_id: int) -> int:
        """Change the model's class and propagate to its assets. Returns count."""
        return ModelAssetClassPropagationHandler.run(
            model=self.model,
            new_asset_class_id=asset_class_id,
            actor=self.actor,
        )

    def update(self, *, data: dict) -> "AssetModel":
        """Apply identity metadata, asset-class change (with propagation),
        and reconcile the linked manufacturer set."""
        m = self.model
        with transaction.atomic():
            changed: list[str] = []
            for field in _METADATA_FIELDS:
                if field in data:
                    value = data[field]
                    if field in ("model_name", "version"):
                        value = (value or "").strip()
                    elif field == "config_baselines":
                        value = list(value or [])
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

    def move_manufacturers(self, *, manufacturer_ids: list[int], direction: str) -> None:
        """Add or remove manufacturers from the linked set, one HTMX move at a time.

        Reconciles through :meth:`_sync_manufacturers`, which preserves exactly one
        primary link (falling back to the first remaining link if the current primary
        is removed)."""
        current = set(
            ModelManufacturer.objects.filter(model=self.model).values_list(
                "manufacturer_id", flat=True
            )
        )
        primary_id = (
            ModelManufacturer.objects.filter(model=self.model, is_primary=True)
            .values_list("manufacturer_id", flat=True)
            .first()
        )
        moved = set(manufacturer_ids)
        desired = current - moved if direction == "remove" else current | moved
        with transaction.atomic():
            self._sync_manufacturers(desired_ids=list(desired), primary_id=primary_id)

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

    def add_config_baseline(self, value: str) -> "AssetModel":
        """Append a new accepted baseline to this model's allow-list (case-insensitive
        dedup). No-op when blank or already present. Backs the asset form's
        "add new baseline" escape hatch."""
        value = (value or "").strip()
        m = self.model
        if not value:
            return m
        existing = {str(v).strip().lower() for v in (m.config_baselines or [])}
        if value.lower() in existing:
            return m
        m.config_baselines = [*(m.config_baselines or []), value]
        m.updated_by = self.actor
        with transaction.atomic():
            m.save(update_fields=["config_baselines", "updated_at", "updated_by"])
        return m

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
