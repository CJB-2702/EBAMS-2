"""Guard type: Validator. Rejects empty alias values and duplicate
(alias_type, normalized_value) pairs — defense in depth alongside the DB
unique constraint (D9)."""

from __future__ import annotations

from app.parts.models import Alias


class AliasValidator:
    @classmethod
    def check(cls, *, alias: str, alias_type: str, normalized_value: str) -> list[str]:
        errors: list[str] = []
        if not (alias or "").strip():
            errors.append("alias value is required.")
        if not (alias_type or "").strip():
            errors.append("alias_type is required.")
        if normalized_value and Alias.objects.filter(
            alias_type=alias_type, normalized_value=normalized_value
        ).exists():
            errors.append(
                f"An alias of type '{alias_type}' with value '{alias}' already exists."
            )
        return errors
