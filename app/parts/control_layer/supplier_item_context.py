"""SupplierItemContext — entry point for one supplier item. No revision
manager, no per-revision document scoping — everything hangs off the single
item thread (D13)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.domain_structs.reverse_structs.supplier_item_struct import (
    SupplierItemStruct,
)
from app.parts.control_layer.managers.supplier_vendor_revision_manager import (
    SupplierVendorRevisionManager,
)
from app.parts.control_layer.thread_domain import default_domain_id_for
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.events.models import ActivityThread

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class SupplierItemContext:
    def __init__(self, item_id: int, actor: "AbstractUser | None" = None) -> None:
        self.actor = actor
        self.item_struct = SupplierItemStruct(item_id)
        self.item = self.item_struct.item

    def struct(self) -> SupplierItemStruct:
        return self.item_struct

    def update(self, *, data: dict) -> "SupplierItem":
        from app.parts.control_layer.managers.supplier_item_manager import SupplierItemManager

        return SupplierItemManager(self.item, self.actor).update(data=data)

    def compatibility_range(self) -> dict:
        i = self.item
        return {
            "min_major": i.min_major_revision_number,
            "min_minor": i.min_minor_revision_number,
            "max_major": i.max_major_revision_number,
            "max_minor": i.max_minor_revision_number,
        }

    def satisfies(self, major: int, minor: int) -> bool:
        """Null-aware compatibility-range rule (D13). All-null = valid for all."""
        i = self.item
        if i.min_major_revision_number is not None:
            if major < i.min_major_revision_number:
                return False
            if major == i.min_major_revision_number and i.min_minor_revision_number is not None:
                if minor < i.min_minor_revision_number:
                    return False
        if i.max_major_revision_number is not None:
            if major > i.max_major_revision_number:
                return False
            if major == i.max_major_revision_number and i.max_minor_revision_number is not None:
                if minor > i.max_minor_revision_number:
                    return False
        return True

    def vendor_revisions(self) -> list[dict]:
        return SupplierVendorRevisionManager(self.item.id, self.actor).list()

    def documents(self) -> list[dict]:
        return self.thread.documents()

    def comments(self) -> list[dict]:
        return self.thread.comments()

    @property
    def thread(self) -> ActivityThreadManager:
        return ActivityThreadManager(
            self.item,
            self.actor,
            domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
        )
