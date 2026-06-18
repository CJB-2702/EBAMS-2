"""CapabilityDefinitionFactory — stateless creation of a CapabilityDefinition root.

Validates name/code uniqueness, then inserts the catalog row with audit
attribution. One transaction. Class/model/asset assignment happens later through
``CapabilityDefinitionContext`` (edit) — create is the bare catalog entry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.guards.capability_definition_uniqueness_guard import (
    CapabilityDefinitionUniquenessValidator,
)
from app.assets.models.capabilities import CapabilityDefinition

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class CapabilityDefinitionValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class CapabilityDefinitionFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> CapabilityDefinition:
        errors = CapabilityDefinitionUniquenessValidator.validate(
            name=data.get("name", ""),
            code=data.get("code", ""),
        )
        if errors:
            raise CapabilityDefinitionValidationError(errors)

        with transaction.atomic():
            return CapabilityDefinition.objects.create(
                name=data["name"].strip(),
                code=data["code"].strip().upper(),
                description=data.get("description") or None,
                is_active=data.get("is_active", True),
                created_by=actor,
                updated_by=actor,
            )
