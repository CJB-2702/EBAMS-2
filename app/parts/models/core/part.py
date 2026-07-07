from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class Part(AuditFieldsMixin):
    """The engineering hub. Part.id is the only thing the wider app references (D3)."""

    part_number = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    part_type = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    # Domain scoping (D14) — default False = visible to all authenticated users.
    is_domain_limited = models.BooleanField(default=False)

    # Lazily created on first comment/attachment (D5).
    thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="part_thread",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "part"
        ordering = ["part_number"]

    def __str__(self) -> str:
        return f"{self.part_number} — {self.name}"
