from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ConfigurationTemplate(AuditFieldsMixin):
    """Standard build specification for an AssetModel."""

    name = models.CharField(max_length=200)
    revision = models.CharField(max_length=20, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.PROTECT,
        related_name="configuration_templates",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "configuration_template"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
