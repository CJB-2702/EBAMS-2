from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class PartType(AuditFieldsMixin):
    """Reference table for standardized part types used in part creation."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "part_type"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
