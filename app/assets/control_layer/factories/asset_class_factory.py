"""AssetClassFactory — stateless creation of an AssetClass root.

Validates name uniqueness, inserts the class with audit attribution, and links
the selected data domains through ``AssetClassDomain``. One transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.guards.asset_class_uniqueness_guard import (
    AssetClassUniquenessValidator,
)
from app.assets.models import AssetClass, AssetClassDomain

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetClassValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class AssetClassFactory:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> AssetClass:
        errors = AssetClassUniquenessValidator.validate(name=data.get("name", ""))
        if errors:
            raise AssetClassValidationError(errors)

        with transaction.atomic():
            asset_class = AssetClass.objects.create(
                name=data["name"].strip(),
                category=data.get("category") or None,
                description=data.get("description") or None,
                restrict_to_domain_set=data.get("restrict_to_domain_set", False),
                meter1_unit=data.get("meter1_unit") or None,
                meter2_unit=data.get("meter2_unit") or None,
                meter3_unit=data.get("meter3_unit") or None,
                meter4_unit=data.get("meter4_unit") or None,
                created_by=actor,
                updated_by=actor,
            )
            cls._link_domains(
                asset_class=asset_class,
                domain_ids=data.get("domain_ids", []),
                actor=actor,
            )
        return asset_class

    @staticmethod
    def _link_domains(*, asset_class, domain_ids, actor) -> None:
        for domain_id in domain_ids:
            AssetClassDomain.objects.create(
                asset_class=asset_class,
                domain_id=domain_id,
                created_by=actor,
                updated_by=actor,
            )
