from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class UserDispatchSkill(AuditFieldsMixin):
    """One record per person per skill — certification level, dates, and
    certificate number. One record per person per skill.

    is_active carries revocation. Not SoftDeleteMixin: a revoked-then-
    recertified person reuses the same row (UNIQUE(user, skill) would refuse
    a second row anyway), so a boolean flag is the whole mechanism — same
    pattern as DispatchSkill.is_active and assets.AssetCapability.is_active.
    Expiry is a separate, orthogonal fact: a lapsed certification is
    surfaced via expires_at, never auto-revoked into is_active=False.
    """

    user = models.ForeignKey(
        "administration.User",
        on_delete=models.CASCADE,
        related_name="dispatch_skills",
    )
    skill = models.ForeignKey(
        "dispatching.DispatchSkill",
        on_delete=models.CASCADE,
        related_name="user_certifications",
    )
    level = models.PositiveSmallIntegerField(null=True, blank=True)
    certified_at = models.DateField(null=True, blank=True)
    expires_at = models.DateField(null=True, blank=True)
    certificate_number = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_dispatch_skill"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill"],
                name="uq_user_dispatch_skill",
            ),
            models.CheckConstraint(
                condition=models.Q(level__isnull=True)
                | (models.Q(level__gte=1) & models.Q(level__lte=5)),
                name="user_dispatch_skill_level_range",
            ),
        ]
        permissions = [
            ("skills_certify", "Can record and revoke a person's skill certifications"),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} — {self.skill_id} (L{self.level or '?'})"
