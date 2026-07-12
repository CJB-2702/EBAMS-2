"""SupplierAliasOrchestrator — fills the Phase 2 create hook (D8). Runs inside
the same transaction as SupplierItemFactory.create."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.control_layer.managers.part_activity_manager import PartActivityManager
from app.parts.control_layer.narrators.alias_narrator import AliasNarrator
from app.parts.models import AliasSource

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Alias, SupplierItem


class SupplierAliasOrchestrator:
    @staticmethod
    def on_supplier_item_created(
        item: "SupplierItem", actor: "AbstractUser | None"
    ) -> "Alias":
        alias = AliasFactory.for_vendor_item(
            item.internal_part,
            item,
            item.manufacturer_part_number,
            "MPN",
            source=AliasSource.AUTO,
            actor=actor,
        )
        PartActivityManager.for_supplier_item(item, actor).record(
            AliasNarrator.alias_added(item.internal_part, alias)
        )
        return alias
