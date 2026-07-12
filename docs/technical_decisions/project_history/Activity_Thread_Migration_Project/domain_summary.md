---
type: "Technical Decision"
title: "Domain Summary — Activity Thread / Event Refactor"
description: "Outline of the **end-state model layer** after the migration."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project]
context_tier: 2
---

> **Superseded.** This doc describes the Phase 3 end-state model layer as a single
> migration. See [phase_3/model_changes.md](phase_3/model_changes.md) for the Phase 3
> build spec. Retained as detailed model reference.

# Domain Summary — Activity Thread / Event Refactor

Outline of the **end-state model layer** after the migration. No logic — file paths,
file names, model class names, and column names only. Reflects D-012 (single table,
`ActivityThread` is a restricted proxy of `Event`).

---

## App location

All thread/event/comment/attachment/file models live in **`app/events/`**.
Other apps (`assets/`, future apps) import from `app.events.models`.

```
app/events/models/
├── __init__.py            ← re-exports public model classes
├── event.py               ← Event (concrete) + ActivityThread (proxy) + managers + enum
├── comment.py             ← Comment
├── attachment.py          ← Attachment
├── file.py                ← File
└── details/               ← per-domain Event "detail" sub-models (unchanged structure)
    ├── administration.py
    ├── asset_management.py
    ├── dispatching.py
    ├── generic.py
    ├── inventory.py
    ├── maintenance.py
    └── system.py
```

---

## `event.py` — Event, ActivityThread, managers, enum

### Module-level constants

| Name | Purpose |
|---|---|
| `_THREAD_SENTINEL = "__thread__"` | Sentinel string written into required CharFields for non-event rows. |

### Enum — `ActivityThreadType(models.TextChoices)`

| Member | Value | Label |
|---|---|---|
| `EVENT` | `"event"` | Event |
| `PHOTO_GALLERY` | `"photo_gallery"` | Photo Gallery |
| `DOCUMENTATION` | `"documentation"` | Documentation |

### Managers

| Class | Bound to | Scope |
|---|---|---|
| `EventManager(models.Manager)` | `Event.objects` | rows where `thread_type == EVENT` |
| `AssetThreadManager(models.Manager)` | `ActivityThread.objects` | rows where `thread_type != EVENT` |
| `AnyThreadManager(models.Manager)` | `Event.threads` | all rows, no filter — context layer only |

Each manager exposes a single overridden method: `get_queryset()`.

### Model — `Event(AuditFieldsMixin, SoftDeleteMixin)`

Concrete model. `db_table = "event"`. Physical store for **all** thread rows.

| Column | Type | Notes |
|---|---|---|
| `id` | `BigAutoField` PK | Explicit. |
| `thread_type` | `CharField(max_length=50, choices=ActivityThreadType.choices, db_index=True)` | Row discriminator. |
| `allow_comments` | `BooleanField(default=True)` | Behavioral flag (D-002). |
| `allow_direct_attachments` | `BooleanField(default=True)` | Behavioral flag (D-002). |
| `domain` | `ForeignKey("administration.Domain", on_delete=PROTECT)` | Required on every row. |
| `title` | `CharField(max_length=255)` | Required; sentinel-filled on non-event rows. |
| `description` | `TextField(blank=True)` | Optional. |
| `event_type` | `CharField(max_length=50)` | Required; sentinel-filled on non-event rows. |
| `status` | `CharField(max_length=50, null=True, blank=True)` | Nullable. |
| `priority` | `CharField(max_length=20, null=True, blank=True)` | Nullable. |
| `event_start` | `DateTimeField()` | Required. |
| `event_end` | `DateTimeField(null=True, blank=True)` | Optional. |
| `created_at` / `updated_at` / `created_by` / `updated_by` | from `AuditFieldsMixin` | Standard audit columns. |
| `deleted_at` | from `SoftDeleteMixin` | Soft-delete flag. |

**Managers attached:**
- `objects = EventManager()`
- `threads = AnyThreadManager()`

**Meta:**
- `db_table = "event"`
- Indexes: on `thread_type`; partial index `(status, event_start)` filtered to `thread_type == "event"`.

### Model — `ActivityThread(Event)`

Restricted **proxy alias** of `Event`. Adds no columns, no behavior beyond:

| Member | Purpose |
|---|---|
| `_SENTINEL_FIELDS` (class attribute, dict) | Maps `title`, `event_type` → `_THREAD_SENTINEL`. |
| `objects = AssetThreadManager()` | Default manager filters out event rows. |
| `save(*args, **kwargs)` | Injects sentinel values for non-event rows before delegating to `Event.save`. |
| `Meta.proxy = True` | Django proxy flag. |

No new columns. Same `db_table = "event"`. Same PK space.

---

## `comment.py` — Comment

```
app/events/models/comment.py → Comment
```

| Column | Type | Notes |
|---|---|---|
| `id` | `BigAutoField` PK | |
| `activity_thread` | `ForeignKey("events.ActivityThread", on_delete=CASCADE, related_name="comments")` | Replaces prior `event` FK (D-004). |
| `parent_comment` | `ForeignKey("self", null=True, blank=True, on_delete=SET_NULL, related_name="replies")` | For revisions/edits chain (existing pattern). |
| `content` | `TextField()` | Comment body. |
| `is_human_made` | `BooleanField(default=True)` | Distinguishes user comments from system-generated. |
| `created_at` / `updated_at` / `created_by` / `updated_by` | audit | |
| `deleted_at` | soft-delete | |

**Meta:** indexes on `(activity_thread, created_at)`.

---

## `attachment.py` — Attachment

Single consolidated model (D-003) — handles both comment-linked and thread-level files.

```
app/events/models/attachment.py → Attachment
```

| Column | Type | Notes |
|---|---|---|
| `id` | `BigAutoField` PK | |
| `thread` | `ForeignKey("events.ActivityThread", on_delete=CASCADE, related_name="attachments")` | Mandatory. |
| `comment` | `ForeignKey("events.Comment", null=True, blank=True, on_delete=SET_NULL, related_name="attachments")` | When null → standalone thread attachment. When set → nested under comment. |
| `file` | `ForeignKey("events.File", on_delete=PROTECT, related_name="attachments")` | Points to file storage record. |
| `display_name` | `CharField(max_length=255, blank=True)` | Optional override of file name. |
| `created_at` / `updated_at` / `created_by` / `updated_by` | audit | |
| `deleted_at` | soft-delete | |

**Meta:** indexes on `(thread, created_at)` and `(comment,)`.

**Service invariant** (enforced in control layer, not DB): `comment.activity_thread_id == thread_id` when `comment` is set.

---

## `file.py` — File

Pure storage record. No thread FK (D-005).

```
app/events/models/file.py → File
```

| Column | Type | Notes |
|---|---|---|
| `id` | `BigAutoField` PK | |
| `uuid` | `UUIDField(default=uuid7, unique=True)` | For external/URL references. |
| `original_name` | `CharField(max_length=255)` | Uploaded filename. |
| `stored_path` | `CharField(max_length=512)` | Path under `MEDIA_ROOT`. |
| `mime_type` | `CharField(max_length=120)` | |
| `size_bytes` | `BigIntegerField()` | |
| `checksum_sha256` | `CharField(max_length=64, blank=True)` | Optional dedup key. |
| `created_at` / `updated_at` / `created_by` / `updated_by` | audit | |
| `deleted_at` | soft-delete | |

---

## `details/` — per-domain Event detail tables

Unchanged structure; one detail model per business domain, linked 1-to-1 to `Event`.
These remain plain `OneToOneField(Event, on_delete=CASCADE, primary_key=True)` rows.

| File | Detail model (suggested name) |
|---|---|
| `administration.py` | `AdministrationEventDetail` |
| `asset_management.py` | `AssetManagementEventDetail` |
| `dispatching.py` | `DispatchingEventDetail` |
| `generic.py` | `GenericEventDetail` |
| `inventory.py` | `InventoryEventDetail` |
| `maintenance.py` | `MaintenanceEventDetail` |
| `system.py` | `SystemEventDetail` |

(Existing names preserved — names listed for completeness only.)

---

## Cross-app FK targets

Downstream models point at the **proxy** (`ActivityThread`), never `Event`, when the
relationship is conceptually "a thread" (D-006, D-008).

| Model | Field | Target |
|---|---|---|
| `assets.Asset` | `photo_gallery` | `OneToOneField("events.ActivityThread", on_delete=PROTECT, related_name="photo_gallery_asset")` |
| `assets.Asset` | `documentation` | `OneToOneField("events.ActivityThread", on_delete=PROTECT, related_name="documentation_asset")` |
| `<various>.DefinedModification` | `activity_thread` | `ForeignKey("events.ActivityThread", on_delete=SET_NULL, null=True)` |
| `<various>.CapabilityDefinition` | `activity_thread` | `ForeignKey("events.ActivityThread", on_delete=SET_NULL, null=True)` |
| `<various>.ConfigurationTemplate` | `activity_thread` | `ForeignKey("events.ActivityThread", on_delete=SET_NULL, null=True)` |

DB column resolves to `event.id` — the proxy shares the table.

---

## Public exports — `app/events/models/__init__.py`

Re-exports the following names for downstream apps to import:

```
ActivityThreadType
Event
ActivityThread
Comment
Attachment
File
```

Detail models are imported via `app.events.models.details.<module>` directly — not re-exported here.

---

## Open questions for review

1. **Soft-delete cascade on `Attachment.comment`:** D-003 specifies `SET_NULL` (demote to thread-level). Confirm UI expects demoted attachments to remain visible in the feed.
2. **`Comment.parent_comment` vs. revision model:** Existing comment code uses a revision chain — confirm whether `parent_comment` stays as the chain link or whether revisions move to a separate `CommentRevision` table.
3. **Indexes on `Attachment(thread, comment)`:** Worth a composite for the "load all attachments for a thread, partition by comment" query path?
4. **`File.checksum_sha256`:** Include now (cheap, useful) or defer until a dedup feature exists?
