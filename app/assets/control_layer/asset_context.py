"""AssetContext — entry point for control logic around one asset id.

Loads an AssetStruct, exposes domain verbs, and delegates to sub-managers
(``meters``, ``hierarchy``). Callers use verbs, never raw ORM.

Extension read/CRUD access lives in the extensions app now
(``AssetDetailExtensionContext``), not on this context — assets is ignorant of
extensions (P2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.domain_structs.asset_struct import AssetStruct
from app.assets.control_layer.guards.asset_serial_number_guard import (
    AssetSerialNumberValidator,
)
from app.assets.control_layer.domain_structs.asset_tree_struct import AssetTreeStruct
from app.assets.control_layer.managers.asset_hierarchy_manager import (
    AssetHierarchyManager,
)
from app.assets.control_layer.managers.asset_relationship_manager import (
    AssetRelationshipManager,
)
from app.events.control_layer.managers.gallery_manager import GalleryManager
from app.assets.control_layer.managers.meter_manager import MeterManager
from app.assets.models import Asset

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class AssetContext:
    def __init__(self, asset_id: int, actor: "AbstractUser", *, eager: bool = False) -> None:
        self.actor = actor
        self.struct = AssetStruct(asset_id, eager=eager)
        self.asset = self.struct.asset

    @classmethod
    def from_struct(cls, struct: AssetStruct, actor: "AbstractUser") -> "AssetContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        ctx.asset = struct.asset
        return ctx

    # ── Sub-managers ─────────────────────────────────────────────────────────
    @property
    def meters(self) -> MeterManager:
        return MeterManager(self.asset, self.actor)

    @property
    def hierarchy(self) -> AssetHierarchyManager:
        return AssetHierarchyManager(self.asset, self.actor)

    @property
    def relationships(self) -> AssetRelationshipManager:
        """Parent/child write path, viewed from this asset as the parent."""
        return AssetRelationshipManager(self.asset, self.actor)

    @property
    def images(self) -> GalleryManager:
        # An Asset is built with its photo_gallery, so lazy creation never fires;
        # the resolver is a safety net that would use the asset's own domain.
        return GalleryManager(
            self.asset,
            self.actor,
            gallery_attr="photo_gallery",
            domain_id_resolver=lambda: self.asset.domain_id,
        )

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def update(self, *, data: dict) -> "Asset":
        """Apply editable metadata (name, serial, status, tags). Serial uniqueness
        is re-validated excluding this asset."""
        a = self.asset
        if "serial_number" in data:
            errors = AssetSerialNumberValidator.validate(
                data["serial_number"], exclude_asset_id=a.id
            )
            if errors:
                raise AssetValidationError(errors)

        changed: list[str] = []
        for field in ("name", "serial_number", "status", "tags", "config_baseline"):
            if field in data:
                value = data[field]
                if field in ("name", "serial_number"):
                    value = (value or "").strip()
                elif field == "config_baseline":
                    # Stored as-is (soft); UI dropdown is the real constraint.
                    value = (value or "").strip() or None
                setattr(a, field, value)
                changed.append(field)

        if changed:
            a.updated_by = self.actor
            with transaction.atomic():
                a.save(update_fields=[*changed, "updated_at", "updated_by"])
        return a

    def record_meters(self, readings: dict[int, float], **kwargs):
        return self.meters.record(readings, **kwargs)

    def tree(self, *, max_depth: int = 2) -> AssetTreeStruct:
        """Nested child tree rooted at this asset, materialized to ``max_depth``."""
        return AssetTreeStruct.from_asset(self.asset, max_depth=max_depth)

    def reparent(self, new_parent_id: int | None) -> None:
        """Set this asset's parent. Routes through the relationship manager so the
        cycle guard, subtree cascade, history row, and dual-linked Event are applied
        on every move (single write path)."""
        if new_parent_id is None:
            current_parent = self.asset.parent_asset
            if current_parent is None:
                return
            AssetRelationshipManager(current_parent, self.actor).detach_child(self.asset.id)
        else:
            new_parent = Asset.objects.get(id=new_parent_id)
            AssetRelationshipManager(new_parent, self.actor).attach_child(self.asset.id)
