"""SupplierItemFactory — creation + the alias hook (D8). No revision row
(D13) — supplier items have no revision table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.guards.supplier_item_validator_guard import (
    SupplierItemValidator,
)
from app.parts.control_layer.narrators.supplier_item_narrator import SupplierItemNarrator
from app.parts.models import Part, SupplierItem

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class SupplierItemValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class SupplierItemFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> SupplierItem:
        errors = SupplierItemValidator.check(
            part_manufacturer_id=data.get("part_manufacturer_id"),
            internal_part_id=data.get("internal_part_id"),
            manufacturer_part_number=data.get("manufacturer_part_number", ""),
        )
        if errors:
            raise SupplierItemValidationError(errors)

        with transaction.atomic():
            item = SupplierItem.objects.create(
                part_manufacturer_id=data["part_manufacturer_id"],
                internal_part_id=data["internal_part_id"],
                manufacturer_part_number=data["manufacturer_part_number"].strip(),
                name=(data.get("name") or "").strip(),
                description=data.get("description") or "",
                is_active=data.get("is_active", True),
                min_major_revision_number=data.get("min_major_revision_number"),
                min_minor_revision_number=data.get("min_minor_revision_number"),
                max_major_revision_number=data.get("max_major_revision_number"),
                max_minor_revision_number=data.get("max_minor_revision_number"),
                created_by=actor,
                updated_by=actor,
            )

            part = Part.objects.get(id=item.internal_part_id)
            SupplierItemNarrator.item_mapped(item, part)

            # Alias hook (D8): mirrors the MPN into an MPN alias.
            from app.parts.control_layer.orchestrators.supplier_alias_orchestrator import (
                SupplierAliasOrchestrator,
            )

            SupplierAliasOrchestrator.on_supplier_item_created(item, actor)

        return item
