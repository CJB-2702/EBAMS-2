---
type: "Technical Decision"
title: "Activity Thread + Event — Limited Proxy design"
description: "Derived from planning session 2026-05-28."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-3]
context_tier: 2
---

> **Superseded.** This doc predates the phased structure. For Phase 3 build specs see
> [phase_3/goal.md](phase_3/goal.md), [phase_3/model_changes.md](phase_3/model_changes.md),
> [phase_3/control_changes.md](phase_3/control_changes.md). This file is retained as
> detailed design reference.

# Activity Thread + Event — Limited Proxy design

Derived from planning session 2026-05-28.
Supersedes the MTI approach described in `decisions.md` D-009.

---

## Problem Statement

The original plan used Django multi-table inheritance (MTI): a separate `activity_thread`
table holding shared thread fields, with `Event` as a subclass adding its own table.

This was rejected for two reasons:

1. **Every Event read issues an implicit JOIN** across two tables for three thread columns
   (`thread_type`, `allow_comments`, `allow_direct_attachments`).
2. **Most rows are Events.** A dedicated thread table would be ~90% redundant — the thread
   row and the event row are almost always fetched together.

The goal is a single physical table that serves as the store for all thread types, keeps
Event fields required and meaningful, and exposes non-overlapping query interfaces for
events vs. asset threads.

---

## Final Design

### One table, two proxy models

The physical table is named `event`. It holds all thread types in a single flat table,
discriminated by `thread_type`. Django proxy models provide the public query interfaces.

```
Physical table: event
┌──────────────────────────────────────────────────────────────────┐
│  id  │ thread_type   │ allow_comments │ allow_direct_attachments │
│      │ title         │ status         │ event_type               │
│      │ priority      │ domain_id      │ event_start │ event_end  │
│      │ ... audit fields ...                                       │
├──────┼───────────────┼────────────────┴──────────────────────────┤
│  1   │ event         │ "Engine overhaul"  status=open  ...       │
│  2   │ event         │ "Brake inspection" status=closed ...      │
│  3   │ photo_gallery │ __thread__  __thread__  NULL  NULL  ...   │
│  4   │ documentation │ __thread__  __thread__  NULL  NULL  ...   │
└──────┴───────────────┴───────────────────────────────────────────┘
```

### Model hierarchy

```
Event  (concrete — db_table = "event")
  │
  └── ActivityThread  (restricted proxy alias — non-event rows only)
```

`Event` is the concrete model and the source of all functionality. `ActivityThread` is a
restricted proxy alias that limits its default manager to non-event rows and auto-fills
sentinel values on save. Neither is a subclass of the other in the DB sense — there is
one table, one PK space, zero JOINs.

The conceptual relationship is: **an ActivityThread IS an Event** — the same row, the same
table, the same PK — just viewed through a restricted lens. The proxy adds no new
capabilities; it restricts the query surface and injects sentinels so that the Event
model's required fields are satisfied for rows that have no meaningful event data.

---

## Model Definitions

```python
# app/events/models/activity_thread.py

_THREAD_SENTINEL = "__thread__"


class ActivityThreadType(models.TextChoices):
    EVENT         = "event",         "Event"
    PHOTO_GALLERY = "photo_gallery", "Photo Gallery"
    DOCUMENTATION = "documentation", "Documentation"


class EventManager(models.Manager):
    """Public manager for Event — returns event rows only."""
    def get_queryset(self):
        return super().get_queryset().filter(thread_type=ActivityThreadType.EVENT)


class AssetThreadManager(models.Manager):
    """Public manager for ActivityThread — returns non-event rows only."""
    def get_queryset(self):
        return super().get_queryset().exclude(thread_type=ActivityThreadType.EVENT)


class AnyThreadManager(models.Manager):
    """Unfiltered. Used internally by EventContext only — never in templates."""
    pass


class Event(AuditFieldsMixin, SoftDeleteMixin):
    # DELIBERATE ANTI-PATTERN: This table is named 'event' but is the physical
    # store for ALL activity thread types. Non-event rows (photo_gallery,
    # documentation) have event-specific fields filled with sentinel values.
    # ActivityThread is a restricted proxy alias over this model.
    #
    # Rationale: >90% of rows are events; a separate thread table would mean a
    # JOIN on every event read for three shared columns. The sentinel approach
    # keeps event fields required and meaningful on actual event rows without
    # polluting the schema with nullable columns. See decisions.md D-012.

    id = models.BigAutoField(primary_key=True)

    # ── Thread fields — present and meaningful on every row ──────────────────
    thread_type              = models.CharField(
        max_length=50,
        choices=ActivityThreadType.choices,
        db_index=True,
    )
    allow_comments           = models.BooleanField(default=True)
    allow_direct_attachments = models.BooleanField(default=True)

    # ── Event fields — required on event rows; sentinel-filled on others ─────
    domain      = models.ForeignKey(
        "administration.Domain",
        on_delete=models.PROTECT,
    )
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type  = models.CharField(max_length=50)
    status      = models.CharField(max_length=50, null=True, blank=True)
    priority    = models.CharField(max_length=20, null=True, blank=True)
    event_start = models.DateTimeField()
    event_end   = models.DateTimeField(null=True, blank=True)

    objects = EventManager()      # Event.objects  → event rows only
    threads = AnyThreadManager()  # Event.threads  → all rows (context layer only)

    class Meta:
        db_table = "event"
        indexes = [
            models.Index(fields=["thread_type"]),
            models.Index(
                fields=["status", "event_start"],
                condition=models.Q(thread_type="event"),
                name="event_status_start_idx",
            ),
        ]


class ActivityThread(Event):
    """
    Restricted proxy alias of Event for non-event rows.

    Restricts the default manager to asset thread rows (photo_gallery,
    documentation, etc.) and auto-fills sentinel values on save so that
    Event's required string fields are satisfied without being nullable.

    All Comment and Attachment FKs point to this proxy — the DB column
    references the 'event' table. The proxy adds no new capabilities.
    """

    _SENTINEL_FIELDS = {
        "title":      _THREAD_SENTINEL,
        "event_type": _THREAD_SENTINEL,
    }

    objects = AssetThreadManager()  # ActivityThread.objects → asset thread rows only

    def save(self, *args, **kwargs):
        if self.thread_type != ActivityThreadType.EVENT:
            for field, sentinel in self._SENTINEL_FIELDS.items():
                if not getattr(self, field):
                    setattr(self, field, sentinel)
        super().save(*args, **kwargs)

    class Meta:
        proxy = True
```

---

## Query Interfaces

Three managers, each with a distinct scope:

| Manager | Accessed via | Returns | Used by |
|---|---|---|---|
| `EventManager` | `Event.objects` | `thread_type = EVENT` rows | Templates, entrypoints, EventContext |
| `AssetThreadManager` | `ActivityThread.objects` | `thread_type != EVENT` rows | Asset entrypoints, AssetHandler |
| `AnyThreadManager` | `Event.threads` | All rows, no filter | `EventContext` internals only |

`Event.objects` and `ActivityThread.objects` are **mutually exclusive** — a row appears in
exactly one of them. `Event.threads` is the escape hatch for the context layer and must
never appear in templates or entrypoints.

```python
# These never overlap:
Event.objects.all()           # events only
ActivityThread.objects.all()  # asset threads only

# Full set — internal context layer use only:
Event.threads.all()
```

---

## Sentinel Values

When `ActivityThread.save()` is called for a non-event row, required string fields are
pre-filled with `"__thread__"` before the write. This satisfies the DB constraint without
making the fields nullable. Fields like `status` and `priority` are nullable and remain
`NULL` for non-event rows. The `domain` FK is required on all rows.

| Field | Event row | Non-event row |
|---|---|---|
| `title` | Required, meaningful | `"__thread__"` |
| `event_type` | Required, meaningful | `"__thread__"` |
| `status` | Optional | `NULL` |
| `priority` | Optional | `NULL` |
| `domain` | Required FK | Required FK (provided at creation) |
| `event_start` | Required, auto-default | auto-default or `NULL` |
| `event_end` | Optional | `NULL` |

The sentinel string `"__thread__"` is intentionally ugly and unlikely to appear in real
data. Any query or display logic that needs to exclude non-event sentinel rows filters on
`thread_type`, not on the sentinel string itself.

---

## Control Layer

`EventContext` is the base context and owns all thread operations (comments, attachments,
file uploads, deletion). `ActivityThreadContext` is a restricted alias — it inherits
everything from `EventContext` with no additions, mirroring the proxy relationship at the
model layer.

`EventContext` fetches rows via `Event.threads` (the unfiltered manager) so that both
contexts resolve any row by `id` without needing separate fetch logic.

```python
class EventContext:
    """
    Full context for any row in the event table. Handles all shared thread
    operations (comments, attachments, file uploads) and event-specific
    operations (create, edit, delete).

    Fetches rows via Event.threads so ActivityThreadContext can inherit
    without overriding the fetch path.
    """
    def __init__(self, id: int, actor=None):
        self._id = id
        self.actor = actor
        self._row = None

    @property
    def row(self) -> Event:
        if self._row is None:
            # AnyThreadManager — resolves any row by id regardless of thread_type.
            self._row = Event.threads.get(pk=self._id)
        return self._row

    @classmethod
    def create_new(cls, post_data, actor) -> "EventContext":
        # Single-row insert — no MTI two-step.
        event = Event.objects.create(
            thread_type=ActivityThreadType.EVENT,
            allow_comments=True,
            allow_direct_attachments=True,
            domain_id=post_data["domain_id"],
            title=post_data["title"].strip(),
            ...
            created_by=actor,
            updated_by=actor,
        )
        ctx = cls(id=event.id, actor=actor)
        ctx._row = event
        return ctx

    def load(self, include_shadow=False) -> EventDetailStruct: ...
    def add_comment(self, content, is_human_made=True) -> Comment: ...
    def edit_comment(self, comment, post_data, files=None) -> CommentResult: ...
    def delete_comment(self, comment) -> None: ...
    def upload_file(self, uploaded_file, comment=None) -> FileResult: ...
    def attach_file(self, file, comment=None, ...) -> Attachment: ...
    def edit(self, post_data) -> EventResult: ...
    def delete(self) -> None: ...


class ActivityThreadContext(EventContext):
    """
    Restricted alias of EventContext for non-event rows.
    Inherits all thread operations as-is — no overrides.
    """
    pass


# Struct alias — ActivityThread rows produce the same struct as Event rows.
ActivityThreadStruct = EventDetailStruct
```

The simplification is intentional: because `ActivityThread` IS `Event` (restricted), there
is nothing for `ActivityThreadContext` to add. Any divergence in future (e.g. asset-thread
specific guards) belongs here as targeted method overrides, not as a parallel base class.

---

## Asset Thread Creation

Asset threads are created via `ActivityThread` (the proxy), not `Event`. Sentinel values
are injected automatically by `ActivityThread.save()`.

```python
class AssetHandler:
    def create(self, post_data, actor) -> AssetResult:
        with transaction.atomic():
            photo_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.PHOTO_GALLERY,
                allow_comments=False,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=actor,
                updated_by=actor,
                # title, event_type → filled with "__thread__" automatically
                # status, priority → left NULL
            )
            doc_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.DOCUMENTATION,
                allow_comments=True,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=actor,
                updated_by=actor,
            )
            asset = Asset.objects.create(
                photo_gallery=photo_thread,
                documentation=doc_thread,
                ...
            )
        return AssetResult(ok=True, asset=asset)
```

---

## FK Targets

All downstream models that reference a thread point to `ActivityThread` (the proxy).
Because the proxy shares the `event` table, the DB column is a FK to `event.id`.

```python
# Comment
activity_thread = models.ForeignKey(
    "events.ActivityThread",
    on_delete=models.CASCADE,
    related_name="comments",
)

# Attachment
thread  = models.ForeignKey("events.ActivityThread", on_delete=models.CASCADE)
comment = models.ForeignKey("events.Comment", on_delete=models.SET_NULL, null=True)

# Asset
photo_gallery = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    related_name="photo_gallery_asset",
)
documentation = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    related_name="documentation_asset",
)
```

Pointing to the proxy rather than the concrete model keeps the intent clear at the model
definition site: these FKs belong to any thread, not specifically to an Event.

---

## Comparison with Rejected MTI Approach

| Concern | MTI (rejected) | STI + proxy (final) |
|---|---|---|
| Physical tables | 2 (`activity_thread` + `event`) | 1 (`event`) |
| Event read | JOIN on every query | Single-row read |
| Event creation | Two-row atomic insert via Django MTI | One `Event.objects.create()` call |
| `event.id == thread.id` | Parent-link magic | Trivially true (same row) |
| Asset thread rows | Plain `activity_thread` rows | Rows in `event` table with sentinels |
| Non-overlapping queries | N/A (different models) | Exclusive proxy managers |
| Migrations complexity | Parent-link column, two tables | Single table |

---

## Decision Record

**D-012** (supersedes D-009):

Event and ActivityThread share a single physical table named `event`. `Event` is the
concrete Django model and the source of all context-layer functionality. `ActivityThread`
is a restricted proxy alias with a manager that excludes event rows and sentinel injection
on save. `ActivityThreadContext` is a thin alias of `EventContext` — it inherits all
thread operations without override. `ActivityThreadStruct` is an exact alias of
`EventDetailStruct`. `Event.objects` returns event rows only. `Event.threads` (unfiltered)
is used exclusively by `EventContext` to resolve any row by `id`. All threads (events and
asset threads) require a `domain` FK. Non-event rows have required string fields (`title`,
`event_type`) filled with the sentinel `"__thread__"` at save time via
`ActivityThread.save()`. Fields like `status` and `priority` are nullable. The `event_start`
field is required; `event_end` is optional.
