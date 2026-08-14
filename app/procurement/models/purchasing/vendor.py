from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class Vendor(AuditFieldsMixin):
    """Commercial supplier a PurchaseOrder is placed with. Deliberately has no
    relationship to parts or manufacturing (D45 superseded) — a vendor may
    resell parts it does not make, or sell nothing part-related at all."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "vendor"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
