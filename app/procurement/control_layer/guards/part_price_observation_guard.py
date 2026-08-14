"""Guard type: Validator. Write-time checks for one price observation row
(D79-D92).

Hard rules raise ProcurementValidationError; an exact-duplicate is a WARNING,
never a hard stop (D80: no unique constraint — two people entering the same
quote is legitimate, and the duplicate just deserves a confirmation).

Domain and part visibility are checked here, against sets the caller derived
from the actor before calling in — this guard never touches request or the
session (§1.5 of the build plan).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.models import PartPriceObservation, PriceConfidence, Vendor


@dataclass(frozen=True)
class DuplicateObservationWarning:
    part_id: int
    existing_observation_id: int
    message: str


class PartPriceObservationValidator:
    @classmethod
    def validate(
        cls,
        *,
        part_id: int,
        vendor_id: int,
        domain_id: int,
        unit_cost: Decimal,
        quantity: Decimal | None,
        observed_at: date,
        confidence: str,
        is_verified: bool,
        visible_part_ids: set[int],
        visible_domain_ids: list[int],
        actor_can_establish: bool,
    ) -> list[DuplicateObservationWarning]:
        """Hard errors raise; duplicates come back as warnings."""
        errors: list[str] = []

        if unit_cost is None or unit_cost < 0:
            errors.append("Unit cost cannot be negative.")
        if quantity is not None and quantity <= 0:
            errors.append("Quantity, if given, must be greater than zero.")
        if observed_at is None or observed_at > date.today():
            errors.append("Observed date cannot be in the future.")
        if not Vendor.objects.filter(pk=vendor_id, is_active=True).exists():
            errors.append("Vendor must exist and be active.")
        if domain_id is None or domain_id not in visible_domain_ids:
            errors.append("Domain is required and must be one you have access to.")
        if part_id not in visible_part_ids:
            errors.append("Part is not visible to you.")
        if confidence not in PriceConfidence.values:
            errors.append("Confidence must be one of the recognized bands.")
        if is_verified and not actor_can_establish:
            # TODO(D89): narrow this to the row's own domain once per-domain
            # establish authority exists — today it is a global permission.
            errors.append(
                "Recording a price as verified requires the price_establish "
                "permission."
            )

        if errors:
            raise ProcurementValidationError(errors)

        return cls._duplicate_warnings(
            part_id=part_id,
            vendor_id=vendor_id,
            domain_id=domain_id,
            observed_at=observed_at,
            unit_cost=unit_cost,
        )

    @staticmethod
    def _duplicate_warnings(
        *,
        part_id: int,
        vendor_id: int,
        domain_id: int,
        observed_at: date,
        unit_cost: Decimal,
    ) -> list[DuplicateObservationWarning]:
        existing = PartPriceObservation.objects.filter(
            part_id=part_id,
            vendor_id=vendor_id,
            domain_id=domain_id,
            observed_at=observed_at,
            unit_cost=unit_cost,
        ).first()
        if existing is None:
            return []
        return [
            DuplicateObservationWarning(
                part_id=part_id,
                existing_observation_id=existing.pk,
                message=(
                    f"An identical observation for this part, vendor, domain, "
                    f"date, and cost already exists (#{existing.pk})."
                ),
            )
        ]
