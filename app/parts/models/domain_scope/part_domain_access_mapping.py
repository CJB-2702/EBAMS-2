from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class PartDomainAccessMapping(AuditFieldsMixin):
    """Which data domains may see a Part and its children (D14). Mirrors UserDomain's
    shape. Only consulted when Part.is_domain_limited is True."""

    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.CASCADE,
        related_name="domain_access_mappings",
    )
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="part_domain_access_mappings",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "part_domain_access_mapping"
        constraints = [
            models.UniqueConstraint(
                fields=["part", "domain"],
                name="uniq_part_domain_access_mapping",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.part_id} → {self.domain_id}"
