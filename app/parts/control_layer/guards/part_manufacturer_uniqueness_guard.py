"""Guard type: Validator. Manufacturer name/code uniqueness."""

from __future__ import annotations

from app.parts.models import PartManufacturer


class PartManufacturerValidator:
    @classmethod
    def check(
        cls, *, name: str, code: str | None, exclude_manufacturer_id: int | None = None
    ) -> list[str]:
        errors: list[str] = []
        name = (name or "").strip()
        if not name:
            errors.append("Manufacturer name is required.")

        qs = PartManufacturer.objects.filter(name=name)
        if exclude_manufacturer_id is not None:
            qs = qs.exclude(id=exclude_manufacturer_id)
        if name and qs.exists():
            errors.append(f"A part manufacturer with name '{name}' already exists.")

        if code:
            qs = PartManufacturer.objects.filter(code=code)
            if exclude_manufacturer_id is not None:
                qs = qs.exclude(id=exclude_manufacturer_id)
            if qs.exists():
                errors.append(f"A part manufacturer with code '{code}' already exists.")

        return errors
