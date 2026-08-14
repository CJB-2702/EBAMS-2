"""ManufacturerContext — entry point for control logic around one manufacturer id.

Owns the update and deactivate verbs. Re-uses the uniqueness validator (excluding
the row being edited) so an edit cannot collide with another manufacturer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.domain_structs.manufacturer_struct import ManufacturerStruct
from app.assets.control_layer.guards.manufacturer_uniqueness_guard import (
    ManufacturerUniquenessValidator,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Manufacturer


class ManufacturerValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ManufacturerContext:
    def __init__(
        self, manufacturer_id: int, actor: "AbstractUser", *, eager: bool = False
    ) -> None:
        self.actor = actor
        self.struct = ManufacturerStruct(manufacturer_id, eager=eager)
        self.manufacturer: "Manufacturer" = self.struct.manufacturer

    @classmethod
    def from_struct(
        cls, struct: ManufacturerStruct, actor: "AbstractUser"
    ) -> "ManufacturerContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        ctx.manufacturer = struct.manufacturer
        return ctx

    # ── Creation ─────────────────────────────────────────────────────────────
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> "Manufacturer":
        from app.assets.models import Manufacturer

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

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def update(self, *, data: dict) -> "Manufacturer":
        """Apply submitted fields after re-checking uniqueness."""
        candidate_name = data.get("name", self.manufacturer.name)
        candidate_code = data.get("code", self.manufacturer.code)
        candidate_website = data.get("website", self.manufacturer.website)

        errors = ManufacturerUniquenessValidator.validate(
            name=candidate_name,
            code=candidate_code,
            website=candidate_website,
            exclude_manufacturer_id=self.manufacturer.id,
        )
        if errors:
            raise ManufacturerValidationError(errors)

        m = self.manufacturer
        changed: list[str] = []
        for field in ("name", "code", "website", "is_active"):
            if field in data:
                value = data[field]
                if field in ("code", "website"):
                    value = value or None
                if field == "name":
                    value = (value or "").strip()
                setattr(m, field, value)
                changed.append(field)

        if changed:
            m.updated_by = self.actor
            with transaction.atomic():
                m.save(update_fields=[*changed, "updated_at", "updated_by"])
        return m
