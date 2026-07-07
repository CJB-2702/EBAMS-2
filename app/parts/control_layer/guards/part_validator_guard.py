"""Guard type: Validator. Single source of truth for Part invariants — shared by
the factory, seed, and any future import path."""

from __future__ import annotations

from app.parts.models import Part


class PartValidator:
    @classmethod
    def check(cls, *, part_number: str, exclude_part_id: int | None = None) -> list[str]:
        errors: list[str] = []
        value = (part_number or "").strip()
        if not value:
            errors.append("part_number is required.")
            return errors
        qs = Part.objects.filter(part_number=value)
        if exclude_part_id is not None:
            qs = qs.exclude(id=exclude_part_id)
        if qs.exists():
            errors.append(f"A part with part_number '{value}' already exists.")
        return errors
