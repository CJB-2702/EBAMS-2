from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionTool


class ActionTool(AbstractActionTool, AuditFieldsMixin, SoftDeleteMixin):
    """
    Tool requirement instance for a live Action step execution.
    """
    action = models.ForeignKey(
        "maintenance.Action",
        on_delete=models.CASCADE,
        related_name="action_tools",
    )
    is_required = models.BooleanField(default=True)
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "maintenance_action_tool"
        ordering = ["sequence_order"]

    def __str__(self) -> str:
        name = self.tool.name if self.tool else self.tool_name
        return f"{name} x{self.quantity_required} (Action: {self.action_id})"
