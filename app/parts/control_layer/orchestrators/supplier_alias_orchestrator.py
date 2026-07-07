"""SupplierAliasOrchestrator — fills the Phase 2 create hook (D8). Runs inside
the same transaction as SupplierItemFactory.create."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.models import AliasSource

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.parts.models import Alias, SupplierItem


class SupplierAliasOrchestrator:
    @staticmethod
    def on_supplier_item_created(
        item: "SupplierItem", actor: "AbstractUser | None"
    ) -> "Alias":
        return AliasFactory.for_vendor_item(
            item.internal_part,
            item,
            item.manufacturer_part_number,
            "MPN",
            source=AliasSource.AUTO,
            actor=actor,
        )
