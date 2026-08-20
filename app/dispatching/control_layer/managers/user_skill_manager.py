"""Manager: certify, update, and revoke a person's DispatchSkill
certifications. Revocation flips UserDispatchSkill.is_active rather than
deleting — see the model docstring."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.skill_certification_guard import (
    SkillCertificationValidator,
)
from app.dispatching.models.skills.user_dispatch_skill import UserDispatchSkill

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class UserSkillValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class UserSkillManager:
    @classmethod
    def certify(cls, *, data: dict, actor: "AbstractUser") -> UserDispatchSkill:
        errors = SkillCertificationValidator.check(
            user_id=data["user_id"],
            skill_id=data["skill_id"],
            level=data.get("level"),
            certified_at=data.get("certified_at"),
            expires_at=data.get("expires_at"),
        )
        if errors:
            raise UserSkillValidationError(errors)

        with transaction.atomic():
            certification = UserDispatchSkill.objects.create(
                user_id=data["user_id"],
                skill_id=data["skill_id"],
                level=data.get("level"),
                certified_at=data.get("certified_at"),
                expires_at=data.get("expires_at"),
                certificate_number=data.get("certificate_number", ""),
                is_active=True,
                created_by=actor,
                updated_by=actor,
            )
        return certification

    @classmethod
    def update(cls, *, user_skill_id: int, data: dict, actor: "AbstractUser") -> UserDispatchSkill:
        certification = UserDispatchSkill.objects.get(pk=user_skill_id)
        errors = SkillCertificationValidator.check(
            user_id=certification.user_id,
            skill_id=certification.skill_id,
            level=data.get("level", certification.level),
            certified_at=data.get("certified_at", certification.certified_at),
            expires_at=data.get("expires_at", certification.expires_at),
            exclude_user_skill_id=user_skill_id,
        )
        if errors:
            raise UserSkillValidationError(errors)

        for field in ("level", "certified_at", "expires_at", "certificate_number"):
            if field in data:
                setattr(certification, field, data[field])
        # Recertifying a revoked row is exactly what "reuses the row" means
        # (see the model docstring) — an edit brings it back to life.
        certification.is_active = True
        certification.updated_by = actor
        certification.save()
        return certification

    @classmethod
    def revoke(cls, *, user_skill_id: int, actor: "AbstractUser") -> UserDispatchSkill:
        certification = UserDispatchSkill.objects.get(pk=user_skill_id)
        certification.is_active = False
        certification.updated_by = actor
        certification.save(update_fields=["is_active", "updated_by", "updated_at"])
        return certification
