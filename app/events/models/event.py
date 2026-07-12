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


# Sentinel written into Event-specific required fields for non-event thread rows.
# Never displayed; signals "this row is not an event" to any raw-SQL reader.
_THREAD_SENTINEL = "__thread__"


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
        user_domain_ids = user.get_all_domain_ids()

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


class FamilyThreadManager(models.Manager):
    """Default manager for a thread proxy — restricts to the thread_types its
    class owns (``_THREAD_TYPES``). The three surface families are disjoint, so
    each proxy sees only its own rows and never another family's."""

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().filter(thread_type__in=self.model._THREAD_TYPES)


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

    # ── Behavior contract ────────────────────────────────────────────────────
    # The class chosen at creation dictates behavior; callers NEVER pass the
    # capability flags. This binds the semantic class name to a fixed behavior:
    #   Event          → event rows,  comments ON,  direct attachments ON
    #   ActivityThread → doc threads, comments ON,  direct attachments ON
    #   FileSet        → file sets,   comments OFF, direct attachments ON
    # Proxy subclasses override these five attributes; save() applies them.
    # The families are disjoint so each proxy manager sees only its own rows.
    _THREAD_TYPES = frozenset({ActivityThreadType.EVENT})
    _DEFAULT_THREAD_TYPE = ActivityThreadType.EVENT
    _ALLOW_COMMENTS = True
    _ALLOW_DIRECT_ATTACHMENTS = True
    _SENTINEL_FIELDS: tuple[tuple[str, str], ...] = ()

    # ── Thread fields — present and meaningful on every row ──────────────────
    thread_type = models.CharField(
        max_length=50,
        choices=ActivityThreadType.choices,
        default=ActivityThreadType.EVENT,
        db_index=True,
    )
    allow_comments = models.BooleanField(default=True)
    allow_direct_attachments = models.BooleanField(default=True)

    # Genuinely per-instance — NOT stamped by save() from a class attr (unlike
    # the capability flags above). When True, standalone file attach/detach on
    # this thread posts a machine comment to its timeline (see
    # ThreadPolicy.narrates_file_changes and DirectAttachmentHandler).
    narrate_file_changes = models.BooleanField(default=False)

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

    def save(self, *args, **kwargs):
        # Class choice drives behavior — the chosen surface class (Event /
        # ActivityThread / FileSet) sets its thread_type family and capability
        # flags here, so no caller ever passes them. Non-event proxies also
        # fill the required Event string fields with a sentinel.
        if self.thread_type not in self._THREAD_TYPES:
            self.thread_type = self._DEFAULT_THREAD_TYPE
        self.allow_comments = self._ALLOW_COMMENTS
        self.allow_direct_attachments = self._ALLOW_DIRECT_ATTACHMENTS
        for field_name, sentinel in self._SENTINEL_FIELDS:
            if not getattr(self, field_name):
                setattr(self, field_name, sentinel)
        super().save(*args, **kwargs)

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
