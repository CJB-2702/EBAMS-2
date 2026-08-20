from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.dispatching.models.abstract_mixins import AbstractSkillRequirement


class DispatchRequestedSkill(AbstractSkillRequirement, AuditFieldsMixin):
    dispatch = models.ForeignKey(
        "events.DispatchingDetail",
        on_delete=models.CASCADE,
        related_name="requested_skills",
    )

    class Meta:
        db_table = "dispatch_requested_skill"
        constraints = [
            models.UniqueConstraint(
                fields=["dispatch", "skill"],
                name="uq_dispatch_requested_skill",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="dispatch_requested_skill_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_level__isnull=True)
                | (models.Q(minimum_level__gte=1) & models.Q(minimum_level__lte=5)),
                name="dispatch_requested_skill_level_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Dispatch #{self.dispatch_id} requires skill {self.skill_id}"
