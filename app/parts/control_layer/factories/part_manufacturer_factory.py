from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.guards.part_manufacturer_uniqueness_guard import (
    PartManufacturerValidator,
)
from app.parts.models import PartManufacturer

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartManufacturerValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class PartManufacturerFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> PartManufacturer:
        errors = PartManufacturerValidator.check(
            name=data.get("name", ""), code=data.get("code")
        )
        if errors:
            raise PartManufacturerValidationError(errors)

        with transaction.atomic():
            manufacturer = PartManufacturer.objects.create(
                name=data["name"].strip(),
                code=(data.get("code") or None),
                website=(data.get("website") or None),
                is_active=data.get("is_active", True),
                created_by=actor,
                updated_by=actor,
            )
        return manufacturer
