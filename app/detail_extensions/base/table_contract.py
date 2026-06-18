"""Abstract primary-table bases (contracts) for extensions.

Every concrete extension table subclasses one of these to receive its owner FK
plus the standard audit columns.
"""

from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetExtensionContract(AuditFieldsMixin):
    """Abstract base for every asset-target extension's primary table."""

    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True


class ModelExtensionContract(AuditFieldsMixin):
    """Abstract base for every model-target extension's primary table."""

    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="+",
    )

    class Meta:
        abstract = True
