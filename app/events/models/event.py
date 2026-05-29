"""Event base model.

The physical table is `event`. All thread types (events and asset threads) share
this one table, discriminated by `thread_type`.

    Event.objects   → thread_type="event" rows only
    Event.threads   → all rows (context layer only, never templates)
    ActivityThread.objects → non-event rows only (photo_gallery, documentation, …)

See Activity_Thread_Migration_Project/phase_3/ for design rationale.
ActivityThread is defined in activity_thread_proxy.py.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone

from app.administration.models.auditable_mixin import AuditFieldsMixin
from app.administration.models.soft_delete_mixin import SoftDeleteMixin


class ActivityThreadType(models.TextChoices):
    EVENT = "event", "Event"
    PHOTO_GALLERY = "photo_gallery", "Photo Gallery"
    DOCUMENTATION = "documentation", "Documentation"


class EventType(models.TextChoices):
    GENERIC = "generic", "Generic"
    SYSTEM = "system", "System"
    ADMINISTRATION = "administration", "Administration"
    ASSET_MANAGEMENT = "asset_management", "Asset Management"
    INVENTORY = "inventory", "Inventory"
    DISPATCHING = "dispatching", "Dispatching"
    MAINTENANCE = "maintenance", "Maintenance"


class EventStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETE = "complete", "Complete"
    CANCELLED = "cancelled", "Cancelled"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    BLOCKED = "blocked", "Blocked"


# Statuses that clear priority on transition.
PRIORITY_CLEARING_STATUSES = {
    EventStatus.COMPLETE,
    EventStatus.CANCELLED,
    EventStatus.FAILED,
    EventStatus.SKIPPED,
}


class EventPriority(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


# ---------------------------------------------------------------------------
# Managers
# ---------------------------------------------------------------------------

class EventQuerySet(models.QuerySet):
    def active(self) -> EventQuerySet:
        return self.filter(deleted_at__isnull=True)

    def deleted(self) -> EventQuerySet:
        return self.filter(deleted_at__isnull=False)

    def visible_to(self, user) -> EventQuerySet:
        """Return events the user may see: in their domains OR created by them."""
        from app.administration.models.data_ownership.user_assignments.user_domains import (
            UserDomain,
        )

        user_domain_ids = UserDomain.objects.filter(
            user=user, is_active=True
        ).values_list("domain_id", flat=True)

        return self.active().filter(
            models.Q(thread_type=ActivityThreadType.EVENT),
            models.Q(domain_id__in=user_domain_ids) | models.Q(created_by=user),
        )


class EventManager(models.Manager):
    """Public manager for Event — returns thread_type=EVENT rows only."""

    def get_queryset(self) -> EventQuerySet:
        return EventQuerySet(self.model, using=self._db).filter(
            thread_type=ActivityThreadType.EVENT
        )

    def active(self) -> EventQuerySet:
        return self.get_queryset().active()

    def visible_to(self, user) -> EventQuerySet:
        return self.get_queryset().visible_to(user)


class AnyThreadManager(models.Manager):
    """Unfiltered. Used internally by EventContext only — never in templates."""
    pass


# ---------------------------------------------------------------------------
# Concrete model
# ---------------------------------------------------------------------------

class Event(AuditFieldsMixin, SoftDeleteMixin):
    # DELIBERATE ANTI-PATTERN: This table is named 'event' but is the physical
    # store for ALL activity thread types. Non-event rows (photo_gallery,
    # documentation) have event-specific fields filled with sentinel values.
    # ActivityThread is a restricted proxy alias over this model.
    #
    # Rationale: >90% of rows are events; a separate thread table would mean a
    # JOIN on every event read for three shared columns. The sentinel approach
    # keeps event fields required and meaningful on actual event rows without
    # polluting the schema with nullable columns.

    # ── Thread fields — present and meaningful on every row ──────────────────
    thread_type = models.CharField(
        max_length=50,
        choices=ActivityThreadType.choices,
        default=ActivityThreadType.EVENT,
        db_index=True,
    )
    allow_comments = models.BooleanField(default=True)
    allow_direct_attachments = models.BooleanField(default=True)

    # ── Event fields — required on event rows; sentinel-filled on others ─────
    domain = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
        related_name="events",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        default=EventType.GENERIC,
    )

    status = models.CharField(
        max_length=20,
        choices=EventStatus.choices,
        null=True,
        blank=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=EventPriority.choices,
        null=True,
        blank=True,
        default=None,
    )

    event_start = models.DateTimeField(null=True, blank=True)
    event_end = models.DateTimeField(null=True, blank=True)

    objects = EventManager()       # Event.objects  → event rows only
    threads = AnyThreadManager()   # Event.threads  → all rows (context layer only)

    class Meta:
        db_table = "event"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "event_start"],
                condition=models.Q(thread_type="event"),
                name="event_status_start_idx",
            ),
        ]

    def _soft_delete(self, actor=None) -> None:
        self.deleted_at = timezone.now()
        update_fields = ["deleted_at"]
        if actor is not None:
            self.updated_by = actor
            update_fields.append("updated_by")
        self.save(update_fields=update_fields)

    def __str__(self) -> str:
        if self.thread_type != ActivityThreadType.EVENT:
            return f"[{self.thread_type}] thread #{self.pk}"
        return f"[{self.get_event_type_display()}] {self.title}"
