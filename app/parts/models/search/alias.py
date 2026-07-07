from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AliasAssociationType(models.TextChoices):
    PART_TO_VENDOR_ITEM = "part_to_vendor_item", "Part to Vendor Item"
    PART_TO_PART = "part_to_part", "Part to Part"
    PART_TO_STRING = "part_to_string", "Part to String"


class AliasSource(models.TextChoices):
    AUTO = "auto", "Auto"
    MANUAL = "manual", "Manual"


class Alias(AuditFieldsMixin):
    """The unified searchable identifier index (D9). Every alias has a forced
    primary `part` anchor — the lookup/resolution column — plus an optional
    typed secondary link governed by `association_type`."""

    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    alias = models.CharField(max_length=200, db_index=True)
    normalized_value = models.CharField(max_length=200, db_index=True)
    alias_type = models.CharField(max_length=50)
    association_type = models.CharField(
        max_length=30,
        choices=AliasAssociationType.choices,
    )
    supplier_item = models.ForeignKey(
        "parts.SupplierItem",
        on_delete=models.CASCADE,
        related_name="aliases",
        null=True,
        blank=True,
    )
    alternate_part = models.ForeignKey(
        "parts.Part",
        on_delete=models.CASCADE,
        related_name="alternate_aliases",
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=10,
        choices=AliasSource.choices,
        default=AliasSource.MANUAL,
    )

    class Meta:
        db_table = "part_alias"
        ordering = ["normalized_value"]
        constraints = [
            models.UniqueConstraint(
                fields=["alias_type", "normalized_value"],
                name="uniq_alias_type_normalized_value",
            ),
            models.CheckConstraint(
                name="alias_association_type_secondary_fk_consistency",
                condition=(
                    models.Q(
                        association_type=AliasAssociationType.PART_TO_VENDOR_ITEM,
                        supplier_item__isnull=False,
                        alternate_part__isnull=True,
                    )
                    | models.Q(
                        association_type=AliasAssociationType.PART_TO_PART,
                        alternate_part__isnull=False,
                        supplier_item__isnull=True,
                    )
                    | models.Q(
                        association_type=AliasAssociationType.PART_TO_STRING,
                        supplier_item__isnull=True,
                        alternate_part__isnull=True,
                    )
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.alias} ({self.alias_type}) → {self.part_id}"
