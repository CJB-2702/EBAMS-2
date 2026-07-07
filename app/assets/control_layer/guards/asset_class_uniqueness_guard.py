"""Guard type: Validator.

Guards AssetClass uniqueness at the write boundary: ``name`` is required and
unique. Serves create (no exclusion) and edit (exclude the row being saved).
"""

from __future__ import annotations

from app.assets.models import AssetClass


class AssetClassUniquenessValidator:
    """Validates duplicate detection for an AssetClass create/edit."""

    @classmethod
    def validate(
        cls,
        *,
        name: str,
        exclude_class_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []

        name = (name or "").strip()
        if not name:
            errors.append("Class name is required.")
            return errors

        qs = AssetClass.objects.filter(name=name)
        if exclude_class_id is not None:
            qs = qs.exclude(id=exclude_class_id)
        if qs.exists():
            errors.append(f"An asset class named '{name}' already exists.")

        return errors
