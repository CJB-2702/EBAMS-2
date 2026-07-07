from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class PartRevisionStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    RELEASED = "released", "Released"
    REDLINE = "redline", "Redline"
    OBSOLETE = "obsolete", "Obsolete"


class PartRevision(AuditFieldsMixin):
    """Flat numeric major/minor revision history (D4). Numbers are the source of
    truth; names are an optional display feature."""

    part = models.ForeignKey(
        "parts.Part",
        on_delete=models.CASCADE,
        related_name="revisions",
    )

    sequence = models.PositiveIntegerField()
    date_of_release = models.DateField(null=True, blank=True)

    major_revision_number = models.PositiveIntegerField()
    minor_revision_number = models.PositiveIntegerField(default=0)
    major_revision_name = models.CharField(max_length=100, null=True, blank=True)
    minor_revision_name = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=PartRevisionStatus.choices,
        default=PartRevisionStatus.DRAFT,
    )
    summary = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    # Lazily created on first comment/attachment (D5).
    thread = models.OneToOneField(
        "events.ActivityThread",
        on_delete=models.PROTECT,
        related_name="part_revision_thread",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "part_revision"
        ordering = ["part", "-major_revision_number", "-minor_revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["part", "major_revision_number", "minor_revision_number"],
                name="uniq_part_revision_major_minor",
            ),
            models.UniqueConstraint(
                fields=["part", "sequence"],
                name="uniq_part_revision_sequence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.part.part_number} rev {self.major_revision_number}.{self.minor_revision_number}"
