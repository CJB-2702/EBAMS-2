from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionTool


class ProtoActionTool(AbstractActionTool, AuditFieldsMixin, SoftDeleteMixin):
    """
    Reusable tool requirement for a ProtoActionItem library step.
    """
    proto_action_item = models.ForeignKey(
        "maintenance.ProtoActionItem",
        on_delete=models.CASCADE,
        related_name="proto_action_tools",
    )
    is_required = models.BooleanField(default=True)
    sequence_order = models.IntegerField(default=1)

    class Meta:
        db_table = "maintenance_proto_action_tool"
        ordering = ["sequence_order"]

    def __str__(self) -> str:
        name = self.tool.name if self.tool else self.tool_name
        return f"{name} x{self.quantity_required} (Proto Item: {self.proto_action_item_id})"
