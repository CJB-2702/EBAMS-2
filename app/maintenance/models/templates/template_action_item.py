from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionItem


class TemplateActionItem(AbstractActionItem, AuditFieldsMixin, SoftDeleteMixin):
    """
    Individual template action items within a TemplateActionSet.
    """
    template_action_set = models.ForeignKey(
        "maintenance.TemplateActionSet",
        on_delete=models.CASCADE,
        related_name="template_action_items",
    )
    proto_action_item = models.ForeignKey(
        "maintenance.ProtoActionItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="template_action_items",
    )
    
    is_required = models.BooleanField(default=True)
    instructions_type = models.CharField(max_length=20, blank=True)
    minimum_staff_count = models.IntegerField(default=1)
    required_skills = models.TextField(blank=True)
    
    sequence_order = models.IntegerField()
    revision = models.CharField(max_length=20, null=True, blank=True)
    prior_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subsequent_revisions",
    )

    class Meta:
        db_table = "maintenance_template_action_item"
        ordering = ["sequence_order"]

    def __str__(self) -> str:
        return f"{self.action_name} (Seq: {self.sequence_order})"
