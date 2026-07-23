from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class Asset(AuditFieldsMixin):
    """A physical (or virtual) tracked entity."""

    name = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=50, default="Active")
    capability_status = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="assets",
    )
    model = models.ForeignKey(
        "assets.AssetModel",
        on_delete=models.PROTECT,
        related_name="assets",
    )

    # DELIBERATE ANTI-PATTERN: denormalized from AssetModel.asset_class.
    # Propagated by ModelAssetClassPropagationHandler when AssetModel.asset_class changes.
    # Integrity-critical enough to keep on Asset directly per old design.
    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="assets",
    )

    # The trim/spec baseline this individual unit is built to (e.g. "LE").
    # CONSTRAINT IS UI-ONLY: interactive components MUST render this as a dropdown
    # sourced from the owning AssetModel.config_baselines allow-list. The DB and
    # control layer intentionally do NOT hard-reject off-list values (soft), so
    # imports / API writes / bulk ingestion never fail on an unknown baseline.
    config_baseline = models.CharField(max_length=200, null=True, blank=True)

    root_asset = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="descendants",
        null=True,
        blank=True,
    )
    parent_asset = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="children",
        null=True,
        blank=True,
    )
    depth_from_root = models.PositiveSmallIntegerField(null=True, blank=True)

    meter1 = models.FloatField(null=True, blank=True)
    meter2 = models.FloatField(null=True, blank=True)
    meter3 = models.FloatField(null=True, blank=True)
    meter4 = models.FloatField(null=True, blank=True)

    photo_gallery = models.OneToOneField(
        "events.FileSet",
        on_delete=models.PROTECT,
        related_name="photo_gallery_asset",
    )
    documentation = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="documentation_asset",
    )

    # Hero image — points at one Attachment in photo_gallery (the single source of
    # truth for images). SET_NULL is a safety net; the gallery manager keeps this
    # in sync (fallback on delete, first-upload auto-primary).
    primary_image = models.ForeignKey(
        "events.Attachment",
        on_delete=models.SET_NULL,
        related_name="primary_of_asset",
        null=True,
        blank=True,
    )

    tags = models.JSONField(null=True, blank=True)
    # No provisioning state lives here — it is tracked in a separate state table
    # owned by the extensions app (P2 / E7). assets owns no such state.

    class Meta:
        db_table = "asset"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["domain"]),
            models.Index(fields=["asset_class"]),
            models.Index(fields=["model"]),
            models.Index(fields=["parent_asset"]),
            models.Index(fields=["root_asset"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.serial_number})"
