"""AssetContext — entry point for control logic around one asset id.

Loads an AssetStruct, exposes domain verbs, and delegates to sub-managers
(``meters``, ``hierarchy``). Callers use verbs, never raw ORM.

Extension read/CRUD access lives in the extensions app now
(``AssetDetailExtensionContext``), not on this context — assets is ignorant of
extensions (P2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.control_layer.domain_structs.asset_struct import AssetStruct
from app.assets.control_layer.managers.asset_hierarchy_manager import (
    AssetHierarchyManager,
)
from app.assets.control_layer.managers.meter_manager import MeterManager

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


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

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def record_meters(self, readings: dict[int, float], **kwargs):
        return self.meters.record(readings, **kwargs)

    def reparent(self, new_parent_id: int | None) -> None:
        self.hierarchy.reparent(new_parent_id)
