from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class DefinedModification(AuditFieldsMixin):
    """Reusable catalog entry for a standardized modification."""

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(null=True, blank=True)
    category = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "defined_modification"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
