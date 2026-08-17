from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractPartDemandRequirement


class TemplatePartDemand(AbstractPartDemandRequirement, AuditFieldsMixin, SoftDeleteMixin):
    """
    Parts required for template action steps.
    """
    template_action_item = models.ForeignKey(
        "maintenance.TemplateActionItem",
        on_delete=models.CASCADE,
        related_name="template_part_demands",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="template_part_demands",
    )
    is_optional = models.BooleanField(default=False)
    sequence_order = models.IntegerField(default=1)

    class Meta:
        db_table = "maintenance_template_part_demand"
        ordering = ["sequence_order"]

    @property
    def is_required(self) -> bool:
        return not self.is_optional

    def __str__(self) -> str:
        return f"{self.part.name} x{self.quantity_required} (Template Item: {self.template_action_item_id})"
