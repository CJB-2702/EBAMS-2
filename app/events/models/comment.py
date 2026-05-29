"""Comment — immutable once saved; edits create a new revision."""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from app.administration.models.traceable_mixin import TraceableHistoryMixin


class CommentQuerySet(models.QuerySet):
    def active(self) -> CommentQuerySet:
        return self.filter(deleted_at__isnull=True)

    def human(self) -> CommentQuerySet:
        return self.filter(is_human_made=True)

    def shadow(self) -> CommentQuerySet:
        return self.filter(is_human_made=False)

    def current_revisions(self) -> CommentQuerySet:
        return self.active()


class CommentManager(models.Manager):
    def get_queryset(self) -> CommentQuerySet:
        return CommentQuerySet(self.model, using=self._db)

    def active(self) -> CommentQuerySet:
        return self.get_queryset().active()

    def visible(self) -> CommentQuerySet:
        return self.get_queryset().active().human()


class Comment(TraceableHistoryMixin):
    """
    A comment on any activity thread (event or asset thread). Never modified in
    place — edits create a new revision. Machine-generated comments have
    is_human_made=False. Shadow history records (field diffs) have deleted_at
    set at creation. Visible machine comments have deleted_at=None.
    """

    activity_thread = models.ForeignKey(
        "events.ActivityThread",
        on_delete=models.CASCADE,
        related_name="comments",
    )

    content = models.TextField()
    is_human_made = models.BooleanField(default=True)

    objects = CommentManager()

    class Meta:
        db_table = "comment"
        ordering = ["created_at"]

    def _soft_delete(self, actor=None) -> None:
        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]
        if actor is not None:
            self.updated_by = actor
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    def __str__(self) -> str:
        prefix = "system" if not self.is_human_made else str(self.created_by)
        return f"Comment #{self.pk} rev{self.revision} by {prefix}"
