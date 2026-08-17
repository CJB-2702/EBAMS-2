from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionItem


class ProtoActionItem(AbstractActionItem, AuditFieldsMixin, SoftDeleteMixin):
    """
    Generic, reusable action definition - standalone library item.
    """
    is_required = models.BooleanField(default=True)
    instructions_type = models.CharField(max_length=20, blank=True)
    minimum_staff_count = models.IntegerField(default=1)
    required_skills = models.TextField(blank=True)
    
    revision = models.CharField(max_length=20, null=True, blank=True)
    prior_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subsequent_revisions",
    )
    
    # Scoped by Domain
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="proto_action_items",
    )

    class Meta:
        db_table = "maintenance_proto_action_item"

    def __str__(self) -> str:
        rev_str = f" (rev {self.revision})" if self.revision else ""
        return f"{self.action_name}{rev_str}"
