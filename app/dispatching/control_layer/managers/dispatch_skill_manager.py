"""Manager: create, edit, deactivate/reactivate DispatchSkill catalogue
entries. No dedicated Factory — creation is validate -> single
.objects.create() -> return, so it lives as a classmethod here rather than
inventing a Factory with no other caller (oop_control_patterns.md §Factory)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.models.skills.dispatch_skill import DispatchSkill

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchSkillValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class DispatchSkillManager:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> DispatchSkill:
        name = (data.get("name") or "").strip()
        if not name:
            raise DispatchSkillValidationError(["Skill name is required."])
        if DispatchSkill.objects.filter(name=name).exists():
            raise DispatchSkillValidationError([f"A skill named '{name}' already exists."])

        with transaction.atomic():
            skill = DispatchSkill.objects.create(
                name=name,
                code=(data.get("code") or None),
                description=data.get("description", ""),
                requires_expiry=data.get("requires_expiry", False),
                is_active=data.get("is_active", True),
                created_by=actor,
                updated_by=actor,
            )
        return skill

    @classmethod
    def update(cls, *, skill_id: int, data: dict, actor: "AbstractUser") -> DispatchSkill:
        skill = DispatchSkill.objects.get(pk=skill_id)
        for field in ("name", "code", "description", "requires_expiry", "is_active"):
            if field in data:
                setattr(skill, field, data[field])
        skill.updated_by = actor
        skill.save()
        return skill

    @classmethod
    def deactivate(cls, *, skill_id: int, actor: "AbstractUser") -> DispatchSkill:
        skill = DispatchSkill.objects.get(pk=skill_id)
        skill.is_active = False
        skill.updated_by = actor
        skill.save(update_fields=["is_active", "updated_by", "updated_at"])
        return skill

    @classmethod
    def reactivate(cls, *, skill_id: int, actor: "AbstractUser") -> DispatchSkill:
        skill = DispatchSkill.objects.get(pk=skill_id)
        skill.is_active = True
        skill.updated_by = actor
        skill.save(update_fields=["is_active", "updated_by", "updated_at"])
        return skill
