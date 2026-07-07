"""PartManager — metadata update verb for a Part root (name, type, category,
description, active/domain-limited flags). Part number changes reuse the same
uniqueness check the create path enforces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.guards.part_validator_guard import PartValidator
from app.parts.models import Part

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


_FIELDS = (
    "part_number",
    "name",
    "description",
    "part_type",
    "category",
    "is_active",
    "is_domain_limited",
)


class PartManager:
    def __init__(self, part: Part, actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def update(self, *, data: dict) -> Part:
        part_number = (data.get("part_number") or "").strip()
        errors = PartValidator.check(part_number=part_number, exclude_part_id=self.part.id)
        if errors:
            raise PartValidationError(errors)

        p = self.part
        with transaction.atomic():
            p.part_number = part_number
            p.name = (data.get("name") or "").strip()
            p.description = data.get("description") or ""
            p.part_type = data.get("part_type") or ""
            p.category = data.get("category") or ""
            p.is_active = data.get("is_active", True)
            p.is_domain_limited = data.get("is_domain_limited", False)
            p.updated_by = self.actor
            p.save(update_fields=[*_FIELDS, "updated_at", "updated_by"])
        return p
