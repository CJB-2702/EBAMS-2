from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionSet


class TemplateActionSet(AbstractActionSet, AuditFieldsMixin, SoftDeleteMixin):
    """
    Template maintenance procedure - container for template actions.
    """
    revision = models.CharField(max_length=20, null=True, blank=True)
    prior_revision = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subsequent_revisions",
    )
    is_active = models.BooleanField(default=True)
    
    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="template_action_sets",
    )
    asset_model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="template_action_sets",
    )
    
    # Domain scoping
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="template_action_sets",
    )

    class Meta:
        db_table = "maintenance_template_action_set"

    def __str__(self) -> str:
        rev_str = f" (rev {self.revision})" if self.revision else ""
        return f"{self.task_name}{rev_str}"
