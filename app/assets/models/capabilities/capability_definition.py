from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class CapabilityDefinition(AuditFieldsMixin):
    """Catalog of capabilities that can be assigned to asset classes, models, and assets."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "capability_definition"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
