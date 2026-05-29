"""ActivityThread proxy — non-event rows in the shared 'event' table.

The physical table is `event`. Rows with thread_type != "event" are asset threads
(photo_gallery, documentation, …). ActivityThread is the restricted proxy alias
that surfaces only those rows and enforces the sentinel-fill contract on save.

    ActivityThread.objects  → non-event rows only
    Comment.activity_thread → FK to this proxy (DB column → event table)
    Attachment.thread       → FK to this proxy (DB column → event table)

Sentinel pattern:
    Event requires title and event_type to be non-blank. Non-event rows satisfy
    that constraint by writing _THREAD_SENTINEL into those fields on save. The
    value is a deliberate placeholder — never shown in the UI.
"""

from __future__ import annotations

from django.db import models

from app.events.models.event import ActivityThreadType, Event

# Sentinel written into Event-specific required fields for non-event thread rows.
# Never displayed; signals "this row is not an event" to any raw-SQL reader.
_THREAD_SENTINEL = "__thread__"


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class AssetThreadManager(models.Manager):
    """Default manager for ActivityThread — excludes event rows."""

    def get_queryset(self) -> models.QuerySet:
        return super().get_queryset().exclude(thread_type=ActivityThreadType.EVENT)


# ---------------------------------------------------------------------------
# Proxy model
# ---------------------------------------------------------------------------

class ActivityThread(Event):
    """
    Restricted proxy alias of Event for non-event rows.

    Adds no new columns — the DB row is identical to an Event row. The proxy
    exists so that Comment and Attachment FKs have a semantically meaningful
    target, and so control-layer code can obtain a correctly filtered queryset
    without manually filtering on thread_type.

    save() auto-fills required Event string fields with _THREAD_SENTINEL so
    that the non-nullable Event constraints are satisfied without schema changes.
    """

    # Event string fields that must be filled for non-event rows.
    _SENTINEL_FIELDS = {
        "title": _THREAD_SENTINEL,
        "event_type": _THREAD_SENTINEL,
    }

    objects = AssetThreadManager()  # ActivityThread.objects → non-event rows only

    def save(self, *args, **kwargs):
        if self.thread_type != ActivityThreadType.EVENT:
            for field, sentinel in self._SENTINEL_FIELDS.items():
                if not getattr(self, field):
                    setattr(self, field, sentinel)
        super().save(*args, **kwargs)

    class Meta:
        proxy = True
