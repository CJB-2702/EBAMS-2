"""ManufacturerFactory — stateless creation of a Manufacturer root.

Validates uniqueness of the natural keys (name, and optional code/website),
then inserts one row with audit attribution. Manufacturer is a global reference
table (no ownership-group scope), so creation is a single statement wrapped in a
transaction for consistency with the other factories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.guards.manufacturer_uniqueness_guard import (
    ManufacturerUniquenessValidator,
)
from app.assets.models import Manufacturer

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class ManufacturerValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ManufacturerFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> Manufacturer:
        errors = ManufacturerUniquenessValidator.validate(
            name=data.get("name", ""),
            code=data.get("code"),
            website=data.get("website"),
        )
        if errors:
            raise ManufacturerValidationError(errors)

        with transaction.atomic():
            manufacturer = Manufacturer.objects.create(
                name=data["name"].strip(),
                code=data.get("code") or None,
                website=data.get("website") or None,
                is_active=data.get("is_active", True),
                created_by=actor,
                updated_by=actor,
            )
        return manufacturer
