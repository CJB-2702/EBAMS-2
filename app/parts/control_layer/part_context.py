"""PartContext — entry point for control logic around one Part id. Delegates
all writes to managers; never mutates models inline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parts.control_layer.domain_structs.part_struct import PartStruct
from app.parts.control_layer.managers.part_domain_manager import PartDomainManager
from app.parts.control_layer.managers.part_manager import PartManager
from app.parts.control_layer.managers.part_revision_manager import PartRevisionManager
from app.parts.control_layer.managers.part_thread_manager import PartThreadManager
from app.parts.models import Part, PartRevision

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartContext:
    def __init__(self, part_id: int, actor: "AbstractUser | None" = None, *, eager: bool = False) -> None:
        self.actor = actor
        self.part_struct = PartStruct(part_id, eager=eager)
        self.part = self.part_struct.part

    @classmethod
    def from_struct(cls, struct: PartStruct, actor: "AbstractUser | None" = None) -> "PartContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.part_struct = struct
        ctx.part = struct.part
        return ctx

    def struct(self) -> PartStruct:
        return self.part_struct

    def update(self, *, data: dict) -> Part:
        return PartManager(self.part, self.actor).update(data=data)

    def current_revision(self) -> PartRevision | None:
        return self.part_struct.current_revision

    def revisions(self) -> list[PartRevision]:
        return list(
            PartRevision.objects.filter(part=self.part).order_by(
                "-major_revision_number", "-minor_revision_number"
            )
        )

    def documents(self, revision: PartRevision | None = None) -> list[dict]:
        owner = revision or self.current_revision()
        if owner is None:
            return []
        return PartThreadManager(owner, self.actor).documents()

    def comments(self, revision: PartRevision | None = None) -> list[dict]:
        owner = revision if revision is not None else self.part
        return PartThreadManager(owner, self.actor).comments()

    def supplier_items(self) -> list:
        """Read-only forward lookup — the Part never depends on supplier items."""
        from app.parts.control_layer.domain_structs.supplier_item_struct import (
            SupplierItemStruct,
        )
        from app.parts.models import SupplierItem

        items = SupplierItem.objects.filter(internal_part=self.part, is_active=True)
        return [SupplierItemStruct.from_instance(item) for item in items]

    @property
    def revisions_manager(self) -> PartRevisionManager:
        return PartRevisionManager(self.part, self.actor)

    @property
    def thread(self) -> PartThreadManager:
        return PartThreadManager(self.part, self.actor)

    @property
    def domain_scope(self) -> PartDomainManager:
        return PartDomainManager(self.part, self.actor)
