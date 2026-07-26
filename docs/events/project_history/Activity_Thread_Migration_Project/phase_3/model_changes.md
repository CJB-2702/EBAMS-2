---
type: "Technical Decision"
title: "Phase 3 — Model Changes"
description: "Three columns are added to the event table."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-3]
context_tier: 2
---

# Phase 3 — Model Changes

---

## `Event` — new columns

Three columns are added to the `event` table. All have defaults so existing rows are
backfilled on a DB reset.

| Column | Type | Default | Purpose |
|---|---|---|---|
| `thread_type` | `CharField(max_length=50, choices=ActivityThreadType.choices, db_index=True)` | `"event"` | Row discriminator — separates event rows from asset thread rows. |
| `allow_comments` | `BooleanField(default=True)` | `True` | Behavioral flag: can human comments be written to this thread? |
| `allow_direct_attachments` | `BooleanField(default=True)` | `True` | Behavioral flag: can files be attached without a comment? |

`thread_type` uses the `ActivityThreadType` enum (see below). The index on `thread_type`
supports the `EventManager` and `AssetThreadManager` queryset filters.

`status` and `priority` should become nullable (they are meaningless on non-event rows).

### `ActivityThreadType` enum (new, in `event.py`)

```python
class ActivityThreadType(models.TextChoices):
    EVENT         = "event",         "Event"
    PHOTO_GALLERY = "photo_gallery", "Photo Gallery"
    DOCUMENTATION = "documentation", "Documentation"
```

---

## New model: `ActivityThread` (proxy of `Event`)

```python
_THREAD_SENTINEL = "__thread__"


class ActivityThread(Event):
    """
    Restricted proxy alias of Event for non-event rows (photo_gallery, documentation, etc).
    Adds no columns. Restricts the default manager to non-event rows and injects sentinel
    values for required Event string fields on save.
    """

    _SENTINEL_FIELDS = {
        "title":      _THREAD_SENTINEL,
        "event_type": _THREAD_SENTINEL,
    }

    objects = AssetThreadManager()  # non-event rows only

    def save(self, *args, **kwargs):
        if self.thread_type != ActivityThreadType.EVENT:
            for field, sentinel in self._SENTINEL_FIELDS.items():
                if not getattr(self, field):
                    setattr(self, field, sentinel)
        super().save(*args, **kwargs)

    class Meta:
        proxy = True
```

### New managers (added to `event.py`)

```python
class EventManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(thread_type=ActivityThreadType.EVENT)


class AssetThreadManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(thread_type=ActivityThreadType.EVENT)


class AnyThreadManager(models.Manager):
    pass  # no filter — used by EventContext internals only
```

Attach to `Event`:
```python
objects = EventManager()       # Event.objects  → event rows only
threads = AnyThreadManager()   # Event.threads  → all rows (context layer only)
```

### Sentinel values

When `ActivityThread.save()` is called for a non-event row, required string fields are
pre-filled with `"__thread__"`. This satisfies DB NOT NULL constraints without making
the fields nullable on the model.

| Field | Event row | Non-event row |
|---|---|---|
| `title` | Required, meaningful | `"__thread__"` |
| `event_type` | Required, meaningful | `"__thread__"` |
| `status` | Optional | `NULL` |
| `priority` | Optional | `NULL` |
| `domain` | Required FK | Required FK (provided at creation) |
| `event_start` | Required | Required (or auto-default) |
| `event_end` | Optional | `NULL` |

---

## `Comment` — FK rename

| Field | Before | After |
|---|---|---|
| `event` | `ForeignKey("events.Event", ...)` | renamed to `activity_thread`, target → `"events.ActivityThread"` |
| DB column | `event_id` | `activity_thread_id` |

```python
activity_thread = models.ForeignKey(
    "events.ActivityThread",
    on_delete=models.CASCADE,
    related_name="comments",
)
```

Pointing at the proxy keeps the intent clear: comments belong to any thread, not
specifically to an Event. The DB column is a FK to `event.id` — same table, same PK.

---

## `Attachment` — FK rename

| Field | Before (Phase 2) | After (Phase 3) |
|---|---|---|
| `event` | `ForeignKey("events.Event", ...)` | renamed to `thread`, target → `"events.ActivityThread"` |
| DB column | `event_id` | `thread_id` |

```python
thread = models.ForeignKey(
    "events.ActivityThread",
    on_delete=models.CASCADE,
    related_name="attachments",
)
```

`comment` FK target updates from `"events.Comment"` (unchanged class, unchanged table) —
no change needed there.

---

## `Asset` — new columns

Two new `OneToOneField` columns on `Asset`:

```python
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

Both are `PROTECT` — thread rows are not deleted when the asset is deleted (they may
carry files). Named explicitly to prevent slot-swapping and to make queries self-documenting.

---

## `__init__.py` — new exports

```python
from .event import ActivityThread, ActivityThreadType
```

Add to the public export list.

---

## Relationship diagram after Phase 3

```
Event  (thread_type="event")
  ├── Comment       (FK comment.activity_thread_id → event.id)
  └── Attachment    (FK attachment.thread_id → event.id, comment_id nullable)

ActivityThread  (thread_type="photo_gallery" | "documentation")
  ├── Comment       (same FK — comment.activity_thread_id → event.id)
  └── Attachment    (same FK — attachment.thread_id → event.id, comment_id nullable)

Asset
  ├── photo_gallery  → ActivityThread (type="photo_gallery")
  └── documentation  → ActivityThread (type="documentation")
```

All FKs resolve to `event.id`. There is one physical table, one PK space, zero JOINs.
