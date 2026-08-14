"""SupplierItemManager — creation and update for a SupplierItem. Owns the
alias hook (D8) on create. No revision row (D13) — supplier items have no
revision table."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.factories.alias_factory import AliasFactory
from app.parts.control_layer.guards.supplier_item_validator_guard import (
    SupplierItemValidator,
)
from app.parts.control_layer.narrators.alias_narrator import AliasNarrator
from app.parts.control_layer.narrators.part_activity_narrator import PartActivityNarrator
from app.parts.control_layer.narrators.supplier_item_narrator import SupplierItemNarrator
from app.parts.models import AliasSource, SupplierItem

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class SupplierItemValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class SupplierItemManager:
    def __init__(self, item: SupplierItem, actor: "AbstractUser | None" = None) -> None:
        self.item = item
        self.actor = actor

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

            # Machine comment onto the base Part's audit feed (§5): the reverse
            # activity struct resolves the item up to its base Part.
            activity = PartActivityNarrator.for_supplier_item(item, actor)
            activity.record(SupplierItemNarrator.item_mapped(item, activity.part))

            # Alias hook (D8): mirrors the MPN into an MPN alias.
            alias = AliasFactory.for_vendor_item(
                item.internal_part,
                item,
                item.manufacturer_part_number,
                "MPN",
                source=AliasSource.AUTO,
                actor=actor,
            )
            activity.record(AliasNarrator.alias_added(item.internal_part, alias))

            cls._sync_simple_part_pointers(item, actor)

        return item

    @staticmethod
    def _sync_simple_part_pointers(item: SupplierItem, actor: "AbstractUser") -> None:
        # Denormalized manufacturer/supplier-item pointers on Part (majority-case
        # lookup shortcut). Only trustworthy when exactly one active SupplierItem
        # exists for the part; otherwise cleared rather than picking arbitrarily.
        active_items = list(
            SupplierItem.objects.filter(internal_part_id=item.internal_part_id, is_active=True)
        )
        part = item.internal_part
        if len(active_items) == 1:
            part.is_simple_part = True
            part.primary_manufacturer_id = active_items[0].part_manufacturer_id
            part.primary_supplier_item_id = active_items[0].id
        else:
            part.is_simple_part = False
            part.primary_manufacturer = None
            part.primary_supplier_item = None
        part.updated_by = actor
        part.save(
            update_fields=[
                "is_simple_part",
                "primary_manufacturer",
                "primary_supplier_item",
                "updated_at",
                "updated_by",
            ]
        )

    def update(self, *, data: dict) -> SupplierItem:
        item = self.item
        errors = SupplierItemValidator.check(
            part_manufacturer_id=data.get("part_manufacturer_id"),
            internal_part_id=data.get("internal_part_id"),
            manufacturer_part_number=data.get("manufacturer_part_number", ""),
            exclude_item_id=item.id,
        )
        if errors:
            raise SupplierItemValidationError(errors)

        with transaction.atomic():
            item.manufacturer_part_number = data["manufacturer_part_number"].strip()
            item.name = (data.get("name") or "").strip()
            item.description = data.get("description") or ""
            item.is_active = data.get("is_active", True)
            item.min_major_revision_number = data.get("min_major_revision_number")
            item.min_minor_revision_number = data.get("min_minor_revision_number")
            item.max_major_revision_number = data.get("max_major_revision_number")
            item.max_minor_revision_number = data.get("max_minor_revision_number")
            item.updated_by = self.actor
            item.save(
                update_fields=[
                    "manufacturer_part_number",
                    "name",
                    "description",
                    "is_active",
                    "min_major_revision_number",
                    "min_minor_revision_number",
                    "max_major_revision_number",
                    "max_minor_revision_number",
                    "updated_at",
                    "updated_by",
                ]
            )
            self._sync_simple_part_pointers(item, self.actor)

        return item
