from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class PartManufacturer(AuditFieldsMixin):
    """External manufacturer registry for purchasable supplier items. Separate
    from assets.Manufacturer on purpose (D2) — parts will have many more vendors
    than asset manufacturers, which must stay fast to look up."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "part_manufacturer"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
