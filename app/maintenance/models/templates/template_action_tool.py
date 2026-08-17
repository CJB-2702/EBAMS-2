from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionTool


class TemplateActionTool(AbstractActionTool, AuditFieldsMixin, SoftDeleteMixin):
    """
    Tools required for a template action step.
    """
    template_action_item = models.ForeignKey(
        "maintenance.TemplateActionItem",
        on_delete=models.CASCADE,
        related_name="template_action_tools",
    )
    is_required = models.BooleanField(default=True)
    sequence_order = models.IntegerField(default=1)

    class Meta:
        db_table = "maintenance_template_action_tool"
        ordering = ["sequence_order"]

    def __str__(self) -> str:
        name = self.tool.name if self.tool else self.tool_name
        return f"{name} x{self.quantity_required} (Template Item: {self.template_action_item_id})"
