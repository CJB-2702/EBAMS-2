from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin


class Tool(AuditFieldsMixin):
    """
    Catalog definition of a tool or specialized equipment item.
    Used for maintenance action requirements, template specifications, and asset servicing.
    """
    name = models.CharField(max_length=200, db_index=True)
    tool_type = models.CharField(max_length=100, blank=True, help_text="e.g. Hand Tool, Power Tool, Measurement, Rigging")
    description = models.TextField(blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    
    manufacturer = models.ForeignKey(
        "parts.PartManufacturer",
        on_delete=models.SET_NULL,
        related_name="tools",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    # Domain Scoping (D14) — default False = visible across all authenticated domains
    is_domain_limited = models.BooleanField(default=False)

    class Meta:
        db_table = "tool"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["tool_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.model_number})" if self.model_number else self.name
