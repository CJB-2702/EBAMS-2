"""Factory: stateless creation of one PartPriceObservation row."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from app.procurement.control_layer.guards.part_price_observation_guard import (
    PartPriceObservationValidator,
)
from app.procurement.models import PartPriceObservation


class PartPriceObservationFactory:
    @classmethod
    def create(
        cls,
        *,
        part_id: int,
        vendor_id: int,
        domain_id: int,
        unit_cost: Decimal,
        observed_at: date,
        source_type: str,
        confidence: str,
        visible_part_ids: set[int],
        visible_domain_ids: list[int],
        actor_can_establish: bool,
        quantity: Decimal | None = None,
        currency: str = "USD",
        is_verified: bool = False,
        source_po_line_id: int | None = None,
        notes: str = "",
        actor=None,
        commit: bool = True,
    ) -> PartPriceObservation:
        """The guard runs first, always — nothing outside this factory (and
        the bulk factory) writes a PartPriceObservation row."""
        PartPriceObservationValidator.validate(
            part_id=part_id,
            vendor_id=vendor_id,
            domain_id=domain_id,
            unit_cost=unit_cost,
            quantity=quantity,
            observed_at=observed_at,
            confidence=confidence,
            is_verified=is_verified,
            visible_part_ids=visible_part_ids,
            visible_domain_ids=visible_domain_ids,
            actor_can_establish=actor_can_establish,
        )

        def _create() -> PartPriceObservation:
            return PartPriceObservation.objects.create(
                part_id=part_id,
                vendor_id=vendor_id,
                domain_id=domain_id,
                unit_cost=unit_cost,
                quantity=quantity,
                currency=currency,
                observed_at=observed_at,
                source_type=source_type,
                confidence=confidence,
                is_verified=is_verified,
                source_po_line_id=source_po_line_id,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )

        if commit:
            with transaction.atomic():
                return _create()
        return _create()
