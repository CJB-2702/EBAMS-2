"""Guard type: Validator. Manufacturer + internal Part must exist; MPN
required; (manufacturer, mpn) must be unique. Compatibility range accepted
as-is in v1 (no min<=max enforcement — D13)."""

from __future__ import annotations

from app.parts.models import Part, PartManufacturer, SupplierItem


class SupplierItemValidator:
    @classmethod
    def check(
        cls,
        *,
        part_manufacturer_id: int | None,
        internal_part_id: int | None,
        manufacturer_part_number: str,
        exclude_item_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []

        if not part_manufacturer_id or not PartManufacturer.objects.filter(
            id=part_manufacturer_id
        ).exists():
            errors.append("A valid part manufacturer is required.")

        if not internal_part_id or not Part.objects.filter(id=internal_part_id).exists():
            errors.append("A valid internal Part is required.")

        mpn = (manufacturer_part_number or "").strip()
        if not mpn:
            errors.append("manufacturer_part_number is required.")
        elif part_manufacturer_id:
            qs = SupplierItem.objects.filter(
                part_manufacturer_id=part_manufacturer_id,
                manufacturer_part_number=mpn,
            )
            if exclude_item_id is not None:
                qs = qs.exclude(id=exclude_item_id)
            if qs.exists():
                errors.append(
                    f"Manufacturer part number '{mpn}' already exists for this manufacturer."
                )

        return errors
