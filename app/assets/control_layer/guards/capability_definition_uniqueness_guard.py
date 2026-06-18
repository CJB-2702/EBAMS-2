"""CapabilityDefinitionUniquenessValidator — name/code uniqueness for the catalog.

Reused by the create factory and the edit context. The edit path passes
``exclude_definition_id`` so a row does not collide with itself.
"""

from __future__ import annotations

from app.assets.models.capabilities import CapabilityDefinition


class CapabilityDefinitionUniquenessValidator:
    @staticmethod
    def validate(
        *,
        name: str,
        code: str,
        exclude_definition_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []
        name = (name or "").strip()
        code = (code or "").strip()

        if not name:
            errors.append("Capability name is required.")
        if not code:
            errors.append("Capability code is required.")
        if errors:
            return errors

        name_qs = CapabilityDefinition.objects.filter(name__iexact=name)
        code_qs = CapabilityDefinition.objects.filter(code__iexact=code)
        if exclude_definition_id is not None:
            name_qs = name_qs.exclude(id=exclude_definition_id)
            code_qs = code_qs.exclude(id=exclude_definition_id)

        if name_qs.exists():
            errors.append(f"A capability named '{name}' already exists.")
        if code_qs.exists():
            errors.append(f"A capability with code '{code}' already exists.")
        return errors
