from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class Manufacturer(AuditFieldsMixin):
    """Company that produces asset models. Extracted from old MakeModel.make."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "manufacturer"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
