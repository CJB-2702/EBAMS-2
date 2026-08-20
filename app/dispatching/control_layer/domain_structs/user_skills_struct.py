"""Struct: aggregated read model for one person's DispatchSkill
certifications — the "my certifications" and "person's certifications"
screens (dispatching_starter_kit/5_roles_and_permissions.md §4.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from app.dispatching.models.skills.user_dispatch_skill import UserDispatchSkill


@dataclass
class UserSkillsStruct:
    user_id: int
    certifications: list[UserDispatchSkill] = field(default_factory=list)

    @classmethod
    def load(cls, *, user_id: int) -> "UserSkillsStruct":
        certifications = list(
            UserDispatchSkill.objects.filter(user_id=user_id)
            .select_related("skill")
            .order_by("skill__name")
        )
        return cls(user_id=user_id, certifications=certifications)

    @property
    def active_certifications(self) -> list[UserDispatchSkill]:
        return [c for c in self.certifications if c.is_active]

    @property
    def expired_certifications(self) -> list[UserDispatchSkill]:
        today = timezone.now().date()
        return [
            c for c in self.active_certifications
            if c.expires_at is not None and c.expires_at < today
        ]

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "certifications": [
                {
                    "id": c.pk,
                    "skill_id": c.skill_id,
                    "skill_name": c.skill.name,
                    "level": c.level,
                    "certified_at": c.certified_at,
                    "expires_at": c.expires_at,
                    "certificate_number": c.certificate_number,
                    "is_active": c.is_active,
                    "is_expired": c in self.expired_certifications,
                }
                for c in self.certifications
            ],
        }
