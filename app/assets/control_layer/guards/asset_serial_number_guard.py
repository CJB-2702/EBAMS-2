"""Guard type: Validator.

Guards Asset.serial_number — presence, basic format, and uniqueness — at the
creation/edit boundary before a row is written.
"""

from __future__ import annotations

from app.assets.models import Asset


class AssetSerialNumberValidator:
    """Validates serial-number presence, shape, and uniqueness."""

    MIN_LENGTH = 1
    MAX_LENGTH = 100

    @classmethod
    def validate(cls, serial_number: str, *, exclude_asset_id: int | None = None) -> list[str]:
        errors: list[str] = []
        value = (serial_number or "").strip()

        if not value:
            errors.append("Serial number is required.")
            return errors
        if len(value) > cls.MAX_LENGTH:
            errors.append(f"Serial number must be at most {cls.MAX_LENGTH} characters.")

        qs = Asset.objects.filter(serial_number=value)
        if exclude_asset_id is not None:
            qs = qs.exclude(id=exclude_asset_id)
        if qs.exists():
            errors.append(f"Serial number '{value}' is already in use.")
        return errors
