"""Guard type: Validator.

Guards Manufacturer uniqueness at the write boundary: ``name`` is required and
unique; ``code`` and ``website``, when supplied, must also be unique. The same
validator serves create (no exclusion) and edit (exclude the row being saved).
"""

from __future__ import annotations

from app.assets.models import Manufacturer


class ManufacturerUniquenessValidator:
    """Validates duplicate detection for a Manufacturer create/edit."""

    @classmethod
    def validate(
        cls,
        *,
        name: str,
        code: str | None,
        website: str | None,
        exclude_manufacturer_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []

        name = (name or "").strip()
        if not name:
            errors.append("Manufacturer name is required.")

        errors.extend(
            cls._unique_or_error(
                field="name",
                label="name",
                value=name,
                exclude_manufacturer_id=exclude_manufacturer_id,
            )
        )
        if code:
            errors.extend(
                cls._unique_or_error(
                    field="code",
                    label="code",
                    value=code,
                    exclude_manufacturer_id=exclude_manufacturer_id,
                )
            )
        if website:
            errors.extend(
                cls._unique_or_error(
                    field="website",
                    label="website",
                    value=website,
                    exclude_manufacturer_id=exclude_manufacturer_id,
                )
            )

        return errors

    @staticmethod
    def _unique_or_error(
        *,
        field: str,
        label: str,
        value: str,
        exclude_manufacturer_id: int | None,
    ) -> list[str]:
        if not value:
            return []
        qs = Manufacturer.objects.filter(**{field: value})
        if exclude_manufacturer_id is not None:
            qs = qs.exclude(id=exclude_manufacturer_id)
        if qs.exists():
            return [f"A manufacturer with {label} '{value}' already exists."]
        return []
