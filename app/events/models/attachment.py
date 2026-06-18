"""Attachment — links a File to an Event, optionally via a Comment."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin
from app.events.utils import generate_uuid7


class AttachmentType(models.TextChoices):
    IMAGE = "image", "Image"
    DOCUMENT = "document", "Document"
    VIDEO = "video", "Video"


class AttachmentQuerySet(models.QuerySet):
    def active(self) -> AttachmentQuerySet:
        return self.filter(deleted_at__isnull=True)


class AttachmentManager(models.Manager):
    def get_queryset(self) -> AttachmentQuerySet:
        return AttachmentQuerySet(self.model, using=self._db)

    def active(self) -> AttachmentQuerySet:
        return self.get_queryset().active()


class Attachment(AuditFieldsMixin, SoftDeleteMixin):
    """
    Links a File to a thread row (Event, ActivityThread, or FileSet — all share
    the `event` table). Optionally also linked to a specific Comment
    (comment_id non-null = comment attachment; comment_id null = standalone attachment).

    FK constraints:
      thread  → CASCADE   (attachment deleted when thread is hard-deleted)
      comment → SET_NULL  (demoted to standalone when comment is deleted)
      file    → PROTECT   (preserves referential integrity in the historical record)
    """

    id = models.UUIDField(primary_key=True, default=generate_uuid7, editable=False)

    thread = models.ForeignKey(
        "events.ActivityThread",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    comment = models.ForeignKey(
        "events.Comment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attachments",
    )
    file = models.ForeignKey(
        "events.File",
        on_delete=models.PROTECT,
        related_name="attachment_links",
    )

    attachment_type = models.CharField(
        max_length=20,
        choices=AttachmentType.choices,
        default=AttachmentType.DOCUMENT,
    )
    caption = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    objects = AttachmentManager()

    class Meta:
        db_table = "attachment"
        ordering = ["display_order", "created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
            models.Index(fields=["comment"]),
        ]

    def _soft_delete(self, actor=None) -> None:
        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]
        if actor is not None:
            self.updated_by = actor
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    def __str__(self) -> str:
        if self.comment_id:
            return f"Attachment {self.id} → Comment {self.comment_id}"
        return f"Attachment {self.id} → Thread {self.thread_id} (standalone)"
