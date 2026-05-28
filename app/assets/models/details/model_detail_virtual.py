from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class ModelDetailVirtual(AuditFieldsMixin):
    """Abstract base for all model-specific detail tables."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True
