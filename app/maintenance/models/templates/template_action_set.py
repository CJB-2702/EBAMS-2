from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.maintenance.models.abstract_mixins import AbstractActionSet


class TemplateActionSet(AbstractActionSet, AuditFieldsMixin, SoftDeleteMixin):
    """
    Template maintenance procedure - container for template actions.
    """
    revision = models.CharField(max_length=20, null=True, blank=True)
    revision_note = models.TextField(
        null=True,
        blank=True,
        help_text="What changed in this revision. Required when publishing a revision of an existing template.",
    )
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
    asset_models = models.ManyToManyField(
        "assets.AssetModel",
        blank=True,
        related_name="template_action_sets",
    )
    
    # Domain scoping
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="template_action_sets",
    )
    
    activity_thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="procedure_template_thread",
    )

    class Meta:
        db_table = "maintenance_template_action_set"

    def __str__(self) -> str:
        rev_str = f" (rev {self.revision})" if self.revision else ""
        return f"{self.task_name}{rev_str}"

    def save(self, *args, **kwargs):
        if not self.activity_thread_id and self.domain_id:
            from app.events.models import ActivityThread
            thread = ActivityThread.objects.create(
                domain_id=self.domain_id,
                created_by=getattr(self, "created_by", None),
                updated_by=getattr(self, "updated_by", None),
            )
            self.activity_thread = thread
        super().save(*args, **kwargs)

