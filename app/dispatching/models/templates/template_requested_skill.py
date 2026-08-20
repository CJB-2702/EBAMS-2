from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractSkillRequirement


class DispatchTemplateRequestedSkill(AbstractSkillRequirement, AuditFieldsMixin):
    revision = models.ForeignKey(
        "dispatching.DispatchTemplateRevision",
        on_delete=models.CASCADE,
        related_name="requested_skills",
    )

    class Meta:
        db_table = "dispatch_template_requested_skill"
        constraints = [
            models.UniqueConstraint(
                fields=["revision", "skill"],
                name="uq_dispatch_template_requested_skill",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="dispatch_template_requested_skill_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_level__isnull=True)
                | (models.Q(minimum_level__gte=1) & models.Q(minimum_level__lte=5)),
                name="dispatch_template_requested_skill_level_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Revision #{self.revision_id} requires skill {self.skill_id}"
