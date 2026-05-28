from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetDetailVirtual(AuditFieldsMixin):
    """Abstract base for all asset-specific detail tables."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True
