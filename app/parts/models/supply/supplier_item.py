from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class SupplierItem(AuditFieldsMixin):
    """A purchasable vendor item mapped forward to exactly one Part (D6/D7). No
    revision table (D13) — vendor history lives as comments on this item's
    thread, and interoperability is a denormalized compatibility range."""

    part_manufacturer = models.ForeignKey(
        "parts.PartManufacturer",
        on_delete=models.PROTECT,
        related_name="supplier_items",
    )
    internal_part = models.ForeignKey(
        "parts.Part",
        on_delete=models.PROTECT,
        related_name="supplier_items",
    )
    manufacturer_part_number = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Compatibility range (D13) — plain ints, no FK to PartRevision. Null = unbounded.
    min_major_revision_number = models.PositiveIntegerField(null=True, blank=True)
    min_minor_revision_number = models.PositiveIntegerField(null=True, blank=True)
    max_major_revision_number = models.PositiveIntegerField(null=True, blank=True)
    max_minor_revision_number = models.PositiveIntegerField(null=True, blank=True)

    # Lazily created on first comment/attachment/vendor-revision (D5, D13).
    thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="supplier_item_thread",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "supplier_item"
        ordering = ["part_manufacturer", "manufacturer_part_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["part_manufacturer", "manufacturer_part_number"],
                name="uniq_supplier_item_mfr_mpn",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.manufacturer_part_number} ({self.part_manufacturer.name})"
