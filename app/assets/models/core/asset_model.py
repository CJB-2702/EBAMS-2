from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetModel(AuditFieldsMixin):
    """
    Product definition for a type of asset. Replaces the old MakeModel.
    Supports a self-referential revision tree: revisions reference a base model.
    """

    model_name = models.CharField(max_length=200)
    subtype_name = models.CharField(max_length=200, null=True, blank=True)
    revision = models.CharField(max_length=100, null=True, blank=True)

    is_base_model = models.BooleanField(default=True)
    base_model = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="revisions",
        null=True,
        blank=True,
    )

    asset_class = models.ForeignKey(
        "assets.AssetClass",
        on_delete=models.PROTECT,
        related_name="models",
    )

    meter1_unit = models.CharField(max_length=100, null=True, blank=True)
    meter2_unit = models.CharField(max_length=100, null=True, blank=True)
    meter3_unit = models.CharField(max_length=100, null=True, blank=True)
    meter4_unit = models.CharField(max_length=100, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    manufacturers = models.ManyToManyField(
        "assets.Manufacturer",
        through="assets.ModelManufacturer",
        related_name="models",
    )
    domains = models.ManyToManyField(
        "administration.Domain",
        through="assets.ModelDomain",
        related_name="asset_models",
    )

    class Meta:
        db_table = "asset_model"
        ordering = ["model_name", "subtype_name"]

    def __str__(self) -> str:
        parts = [self.model_name]
        if self.subtype_name:
            parts.append(self.subtype_name)
        if self.revision:
            parts.append(f"rev {self.revision}")
        return " — ".join(parts)
