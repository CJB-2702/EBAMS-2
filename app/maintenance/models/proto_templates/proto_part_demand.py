from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractPartDemandRequirement


class ProtoPartDemand(AbstractPartDemandRequirement, AuditFieldsMixin, SoftDeleteMixin):
    """
    Reusable part requirement for a ProtoActionItem library step.
    """
    proto_action_item = models.ForeignKey(
        "maintenance.ProtoActionItem",
        on_delete=models.CASCADE,
        related_name="proto_part_demands",
    )
    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="proto_part_demands",
    )
    is_optional = models.BooleanField(default=False)
    sequence_order = models.IntegerField(default=1)

    class Meta:
        db_table = "maintenance_proto_part_demand"
        ordering = ["sequence_order"]

    @property
    def is_required(self) -> bool:
        return not self.is_optional

    def __str__(self) -> str:
        return f"{self.part.name} x{self.quantity_required} (Proto Item: {self.proto_action_item_id})"
