"""Guard type: Validator. Input and invariant checks for a UserDispatchSkill
row at the boundary — friendly pre-checks in front of the DB-level
UNIQUE(user, skill) and level-range constraints (build_phase_1_models.md §5).
"""

from __future__ import annotations

from app.dispatching.models.skills.dispatch_skill import DispatchSkill
from app.dispatching.models.skills.user_dispatch_skill import UserDispatchSkill


class SkillCertificationValidator:
    @classmethod
    def check(
        cls,
        *,
        user_id: int,
        skill_id: int,
        level: int | None,
        certified_at=None,
        expires_at=None,
        exclude_user_skill_id: int | None = None,
    ) -> list[str]:
        errors: list[str] = []

        skill = DispatchSkill.objects.filter(pk=skill_id).first()
        if skill is None:
            errors.append("Skill does not exist.")
        elif not skill.is_active:
            errors.append(f"Skill '{skill.name}' is not active.")

        if level is not None and not (1 <= level <= 5):
            errors.append("Level must be between 1 and 5.")

        if skill is not None and skill.requires_expiry and expires_at is None:
            errors.append(f"Skill '{skill.name}' requires an expiry date.")

        if certified_at and expires_at and expires_at < certified_at:
            errors.append("Expiry date cannot be before the certification date.")

        qs = UserDispatchSkill.objects.filter(user_id=user_id, skill_id=skill_id)
        if exclude_user_skill_id is not None:
            qs = qs.exclude(pk=exclude_user_skill_id)
        if qs.exists():
            errors.append("This person already has a certification record for this skill.")

        return errors
