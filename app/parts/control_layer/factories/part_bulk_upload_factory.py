"""PartBulkUploadFactory — the /parts/bulk-upload/ paste-grid's row-by-row
creation. Each row is a whole simple part: identity + one manufacturer +
one supplier item, mirroring PartCreationWizardFactory's "at least one
manufacturer/supplier item" rule (§ part_create). The supplier item's
name/description are duplicated straight from the part's own name/description
— the grid has no separate columns for them.

Each row runs in its own transaction so one bad row doesn't roll back the
rest of the paste."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction

from app.administration.models import Domain
from app.parts.control_layer.errors import PartValidationError
from app.parts.control_layer.factories.part_factory import PartFactory
from app.parts.control_layer.managers.part_domain_manager import PartDomainManager
from app.parts.control_layer.managers.part_manufacturer_manager import (
    PartManufacturerManager,
    PartManufacturerValidationError,
)
from app.parts.control_layer.managers.supplier_item_manager import (
    SupplierItemManager,
    SupplierItemValidationError,
)
from app.parts.models import Part, PartManufacturer

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@dataclass
class BulkUploadRowResult:
    row_index: int
    part_number: str
    ok: bool
    part_id: int | None = None
    errors: list[str] | None = None


class PartBulkUploadFactory:
    @classmethod
    def create_many(
        cls,
        *,
        rows: list[dict],
        actor: "AbstractUser",
        domain_ids: list[int] | None = None,
    ) -> list[BulkUploadRowResult]:
        # Resolved once up front (not per-row) — every part in the upload gets the same
        # domain set, and a stale/deleted domain id should be dropped silently rather than
        # failing every row in the file.
        valid_domain_ids = (
            list(Domain.objects.filter(id__in=domain_ids).values_list("id", flat=True))
            if domain_ids
            else []
        )
        results = []
        for index, row in enumerate(rows):
            results.append(
                cls._create_row(row_index=index, row=row, actor=actor, domain_ids=valid_domain_ids)
            )
        return results

    @classmethod
    def _create_row(
        cls, *, row_index: int, row: dict, actor: "AbstractUser", domain_ids: list[int]
    ) -> BulkUploadRowResult:
        errors = cls._row_errors(row)
        if errors:
            return BulkUploadRowResult(
                row_index=row_index, part_number=row["part_number"], ok=False, errors=errors
            )

        try:
            with transaction.atomic():
                manufacturer = cls._resolve_manufacturer(row["manufacturer"], actor)

                part = PartFactory.create(
                    data={
                        "part_number": row["part_number"],
                        "name": row["name"],
                        "description": row["description"],
                        "part_type": row["part_type"],
                        "category": row["category"],
                    },
                    actor=actor,
                )

                SupplierItemManager.create(
                    actor=actor,
                    data={
                        "internal_part_id": part.id,
                        "part_manufacturer_id": manufacturer.id,
                        "manufacturer_part_number": row["manufacturer_part_number"],
                        "name": row["name"],
                        "description": row["description"],
                    },
                )

                for domain_id in domain_ids:
                    PartDomainManager(part, actor).add_domain(domain_id)
        except (PartValidationError, SupplierItemValidationError, PartManufacturerValidationError) as exc:
            return BulkUploadRowResult(
                row_index=row_index, part_number=row["part_number"], ok=False, errors=exc.errors
            )

        return BulkUploadRowResult(row_index=row_index, part_number=row["part_number"], ok=True, part_id=part.id)

    @staticmethod
    def _row_errors(row: dict) -> list[str]:
        errors = []
        if not row["part_number"]:
            errors.append("Part number is required.")
        if not row["name"]:
            errors.append("Name is required.")
        if not row["manufacturer"]:
            errors.append("Manufacturer is required.")
        if not row["manufacturer_part_number"]:
            errors.append("Manufacturer part number is required.")
        return errors

    @staticmethod
    def _resolve_manufacturer(name: str, actor: "AbstractUser") -> PartManufacturer:
        existing = PartManufacturer.objects.filter(name__iexact=name).first()
        if existing:
            return existing
        return PartManufacturerManager.create(data={"name": name}, actor=actor)
