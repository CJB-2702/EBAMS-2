"""BulkFactory: the grid's commit path. Validates every row, then writes all
or none — a grid that half-saves is worse than one that fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.guards.part_price_observation_guard import (
    DuplicateObservationWarning,
    PartPriceObservationValidator,
)
from app.procurement.models import PartPriceObservation


@dataclass(frozen=True)
class PriceObservationInput:
    part_id: int
    vendor_id: int
    domain_id: int
    unit_cost: Decimal
    observed_at: date
    source_type: str
    confidence: str
    quantity: Decimal | None = None
    currency: str = "USD"
    is_verified: bool = False
    source_po_line_id: int | None = None
    notes: str = ""


@dataclass(frozen=True)
class BulkObservationResult:
    created_ids: list[int]
    warnings: list[DuplicateObservationWarning]
    #: Rows the adaptor dropped upstream for having no cost — carried through
    #: so the page can list them by part number rather than silently losing
    #: them, never populated by this factory itself.
    dropped_part_ids: list[int] = field(default_factory=list)


class PartPriceObservationBulkFactory:
    @classmethod
    def create_many(
        cls,
        *,
        rows: list[PriceObservationInput],
        actor,
        visible_part_ids: set[int],
        visible_domain_ids: list[int],
        actor_can_establish: bool,
        dropped_part_ids: list[int] | None = None,
    ) -> BulkObservationResult:
        errors: list[str] = []
        warnings: list[DuplicateObservationWarning] = []

        for index, row in enumerate(rows):
            try:
                warnings.extend(
                    PartPriceObservationValidator.validate(
                        part_id=row.part_id,
                        vendor_id=row.vendor_id,
                        domain_id=row.domain_id,
                        unit_cost=row.unit_cost,
                        quantity=row.quantity,
                        observed_at=row.observed_at,
                        confidence=row.confidence,
                        is_verified=row.is_verified,
                        visible_part_ids=visible_part_ids,
                        visible_domain_ids=visible_domain_ids,
                        actor_can_establish=actor_can_establish,
                    )
                )
            except ProcurementValidationError as exc:
                errors.extend(f"Row {index + 1}: {message}" for message in exc.errors)

        if errors:
            raise ProcurementValidationError(errors)

        with transaction.atomic():
            objects = [
                PartPriceObservation(
                    part_id=row.part_id,
                    vendor_id=row.vendor_id,
                    domain_id=row.domain_id,
                    unit_cost=row.unit_cost,
                    quantity=row.quantity,
                    currency=row.currency,
                    observed_at=row.observed_at,
                    source_type=row.source_type,
                    confidence=row.confidence,
                    is_verified=row.is_verified,
                    source_po_line_id=row.source_po_line_id,
                    notes=row.notes,
                    created_by=actor,
                    updated_by=actor,
                )
                for row in rows
            ]
            created = PartPriceObservation.objects.bulk_create(objects)

        return BulkObservationResult(
            created_ids=[obj.pk for obj in created],
            warnings=warnings,
            dropped_part_ids=list(dropped_part_ids or []),
        )
