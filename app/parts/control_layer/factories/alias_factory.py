"""AliasFactory — the single alias write path (D9). The only creator of
Alias rows, so association_type/secondary-FK selection and normalization live
in one place."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.guards.alias_validator_guard import AliasValidator
from app.parts.models import Alias, AliasAssociationType, AliasSource, Part, SupplierItem

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AliasValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


def _normalize(value: str) -> str:
    return (value or "").strip().casefold()


class AliasFactory:
    @classmethod
    def for_string(
        cls,
        part: Part,
        alias: str,
        alias_type: str,
        *,
        source: str = AliasSource.MANUAL,
        actor: "AbstractUser | None" = None,
    ) -> Alias:
        return cls._create(
            part=part,
            alias=alias,
            alias_type=alias_type,
            association_type=AliasAssociationType.PART_TO_STRING,
            source=source,
            actor=actor,
        )

    @classmethod
    def for_vendor_item(
        cls,
        part: Part,
        item: SupplierItem,
        alias: str,
        alias_type: str,
        *,
        source: str = AliasSource.MANUAL,
        actor: "AbstractUser | None" = None,
    ) -> Alias:
        return cls._create(
            part=part,
            alias=alias,
            alias_type=alias_type,
            association_type=AliasAssociationType.PART_TO_VENDOR_ITEM,
            source=source,
            actor=actor,
            supplier_item=item,
        )

    @classmethod
    def for_alternate_part(
        cls,
        part: Part,
        alternate_part: Part,
        alias: str,
        alias_type: str,
        *,
        source: str = AliasSource.MANUAL,
        actor: "AbstractUser | None" = None,
    ) -> Alias:
        return cls._create(
            part=part,
            alias=alias,
            alias_type=alias_type,
            association_type=AliasAssociationType.PART_TO_PART,
            source=source,
            actor=actor,
            alternate_part=alternate_part,
        )

    @classmethod
    def _create(
        cls,
        *,
        part: Part,
        alias: str,
        alias_type: str,
        association_type: str,
        source: str,
        actor,
        supplier_item: SupplierItem | None = None,
        alternate_part: Part | None = None,
    ) -> Alias:
        normalized_value = _normalize(alias)
        errors = AliasValidator.check(
            alias=alias, alias_type=alias_type, normalized_value=normalized_value
        )
        if errors:
            raise AliasValidationError(errors)

        with transaction.atomic():
            return Alias.objects.create(
                part=part,
                alias=alias.strip(),
                normalized_value=normalized_value,
                alias_type=alias_type,
                association_type=association_type,
                supplier_item=supplier_item,
                alternate_part=alternate_part,
                source=source,
                created_by=actor,
                updated_by=actor,
            )
