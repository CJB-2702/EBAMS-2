# Activity Thread Architecture — Domain Changes Plan

Derived from planning session 2026-05-27.
See `Initial_concepts/` for prior concept and refactoring notes.

---

## Decisions Log

| Decision | Choice | Notes |
|---|---|---|
| ActivityThread app location | `events/`, re-exported | All apps import from `events.models` |
| Thread behavior | Two explicit flags: `allow_comments`, `allow_direct_attachments` | `thread_type` is a label only; all service-layer gates check flags, not type |
| Event → Thread relationship | Django multi-table inheritance (MTI) | Event subclasses ActivityThread; `event.pk == activity_thread.pk` automatically; single `Event.objects.create()` call |
| Comment parent | `Comment.activity_thread` replaces `Comment.event` | Uniform across all entity types |
| File anchoring | File stays standalone | File has no FK to thread; Attachment is the link |
| Attachment model | Dual reference: mandatory `thread_id`, nullable `comment_id` | Files can exist at thread level without a comment; comment deletion demotes to thread-level (SET NULL) |
| Asset threads | Two explicit OneToOneFields on Asset | `photo_gallery` and `documentation`, both eager-created |
| Asset thread creation | Eager (on Asset creation) | Eliminates race conditions; thread always exists |
| anchor_event replacement | `activity_thread` FK on asset detail models | Replaces the planned `anchor_event` FK entirely |

---

## New Model: ActivityThread

**File:** `app/events/models/activity_thread.py`

```python
class ActivityThreadType(models.TextChoices):
    EVENT         = "event",         "Event Thread"
    PHOTO_GALLERY = "photo_gallery", "Photo Gallery"
    DOCUMENTATION = "documentation", "Documentation"

class ActivityThread(AuditFieldsMixin):
    thread_type              = models.CharField(max_length=50, choices=ActivityThreadType.choices)
    allow_comments           = models.BooleanField(default=True)
    allow_direct_attachments = models.BooleanField(default=True)

    class Meta:
        db_table = "activity_thread"
```

`thread_type` is a label for display and filtering only. All service-layer gates check
the flags:
- `allow_comments=False` → `ActivityThreadContext.add_comment()` raises
- `allow_direct_attachments=False` → `ActivityThreadContext.upload_file()` raises when `comment=None`

**Conventions by thread purpose:**

| Purpose | `allow_comments` | `allow_direct_attachments` |
|---|---|---|
| Event thread | True | True |
| Photo gallery | False | True |
| Documentation | True | True |

**Deferred:** `table_thread_for` column (identifies owning entity type). Not needed now.

---

## Model Renames

| Old class | New class | Old db_table | New db_table |
|---|---|---|---|
| `EventFile` | `File` | `event_file` | `file` |
| `EventComment` | `Comment` | `event_comment` | `comment` |
| `CommentAttachment` | `Attachment` | `event_comment_attachment` | `attachment` |

Pure renames — no schema changes beyond the table name and the FK changes below.

---

## Attachment Model: Schema Change

Current: `CommentAttachment.comment_id` is mandatory; no thread FK.

New schema:

```python
class Attachment(AuditFieldsMixin, SoftDeleteMixin):
    id         = UUIDField(primary_key=True, default=generate_uuid7)
    thread     = FK(ActivityThread, CASCADE, related_name="attachments")   # mandatory
    comment    = FK(Comment, SET_NULL, null=True, related_name="attachments")  # nullable
    file       = FK(File, PROTECT, related_name="attachment_links")
    attachment_type = CharField(choices=AttachmentType)
    caption    = CharField(max_length=255, blank=True)
    display_order = PositiveIntegerField(default=0)
```

Key behavioral rule: when a comment is deleted, its attachments are NOT deleted — they fall
back to thread-level (SET NULL fires). This preserves the file record in the audit trail.
The service layer must enforce cross-thread integrity: `attachment.comment.thread_id` must
match `attachment.thread_id` before any insert.

---

## Comment Model: FK Change

```python
# Before
event = FK("events.Event", CASCADE, related_name="comments")

# After
activity_thread = FK("events.ActivityThread", CASCADE, related_name="comments")
```

`Comment.is_human_made` stays. Machine comments (shadow diffs, status transitions) are now
written to the event's thread by the EventHandler rather than directly to the Event.

---

## Event Model: Multi-Table Inheritance from ActivityThread

```python
class Event(ActivityThread, SoftDeleteMixin):
    domain      = models.ForeignKey("administration.Domain", ...)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    event_type  = models.CharField(...)
    status      = models.CharField(...)
    priority    = models.CharField(...)
    event_start = models.DateTimeField(null=True, blank=True)
    event_end   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "event"
```

Django MTI automatically creates `activitythread_ptr_id` on the `event` table as its PK
and FK to `activity_thread`. `event.pk == activity_thread.pk` is guaranteed by the DB.

`event.allow_comments` and `event.allow_direct_attachments` are accessible directly as
inherited fields — no traversal needed.

Creation is a single call — Django inserts both rows atomically:
```python
event = Event.objects.create(
    allow_comments=True,
    allow_direct_attachments=True,
    domain_id=...,
    title=...,
    created_by=actor,
    updated_by=actor,
)
# event.pk == activity_thread row PK, guaranteed
```

Rescue invariant: `ActivityThread.objects.get(pk=n)` and `Event.objects.get(pk=n)` always
refer to the same logical entity. If the event row is missing, the thread row survives and
can be identified for cleanup.

---

## Asset Model: Add two thread FKs

```python
photo_gallery = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    null=True,
    related_name="photo_gallery_asset",
)
documentation = models.OneToOneField(
    "events.ActivityThread",
    on_delete=models.PROTECT,
    null=True,
    related_name="documentation_asset",
)
```

Both threads are created eagerly when the Asset is created (inside the asset creation handler
transaction). `photo_gallery` is created with `allow_comments=False`; `documentation` with
`allow_comments=True`.

`AssetImage` is removed. Photos are now Files attached via Attachment to the `photo_gallery` thread.

---

## Asset Detail Models: Replace anchor_event with activity_thread

The planned `anchor_event` FK on these models is replaced with an `activity_thread` FK.
None of these changes existed in the codebase yet — this is greenfield.

| Model | File |
|---|---|
| `DefinedModification` | `app/assets/models/configurations/defined_modification.py` |
| `CapabilityDefinition` | `app/assets/models/capabilities/capability_definition.py` |
| `ConfigurationTemplate` | `app/assets/models/configurations/configuration_template.py` |

```python
activity_thread = models.ForeignKey(
    "events.ActivityThread",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="<model_name>_set",
)
```

---

## Implementation Phases

### Phase 1 — ActivityThread model
- Create `app/events/models/activity_thread.py`
- Export from `app/events/models/__init__.py`
- No schema changes to existing tables

### Phase 2 — Rename EventFile → File, EventComment → Comment, CommentAttachment → Attachment
Blast radius (~12 files):
- `app/events/models/file.py`, `comment.py`, `attachment.py` — class + `db_table` rename
- `app/events/models/__init__.py`
- `app/events/admin.py`
- `app/events/control_layer/handlers/comment_handler.py`, `file_handler.py`
- `app/events/control_layer/comment_context.py`, `file_context.py`
- `app/events/control_layer/domain_structs/*.py`
- `app/events/presentation_layer/entrypoints/comments.py`, `files.py`
- `app/events/presentation_layer/tools/file_previews.py`
- Any `assets/` imports referencing `EventFile`

### Phase 3 — Attachment schema: add thread FK, make comment nullable
- Update `Attachment` model with dual `thread_id` + nullable `comment_id`
- Service-layer cross-thread integrity check (see `control_layer_services.md`)

### Phase 4 — Comment: swap event FK for activity_thread FK
- `Comment.event` → `Comment.activity_thread`
- `event_handler.py`: `_apply_shadow_comment`, `_apply_machine_comment` receive thread, not event
- `comment_context.py`, `comment_handler.py`: update FK lookups

### Phase 5 — Event: add activity_thread FK
- Add `Event.activity_thread` FK
- `EventHandler.create()`: create ActivityThread(EVENT, allow_comments=True) first, then Event
- `EventContext`: assemble thread data via ActivityThreadContext, expose on EventDetailStruct
- Templates: `event.comments.all()` → `event_struct.comments` (EventContext mediates, callers unchanged)

### Phase 6 — Asset: add photo_gallery + documentation threads
- Add two OneToOneFields to `Asset`
- Asset creation handler: create two ActivityThread rows before creating Asset
- Remove `AssetImage` model and all imports

### Phase 7 — Asset detail models: add activity_thread FK
- `DefinedModification`, `CapabilityDefinition`, `ConfigurationTemplate`

### Phase 8 — DB rebuild
```bash
python dev_tools/delete_database_rebuild_models.py --seed
```

### Phase 9 — Update docs
- `docs/Events/` — remove `EventFile`/`EventComment`/`CommentAttachment` references
- `docs/applications/assets/` — document photo_gallery and documentation threads

---

## Out of Scope

- UI/templates for photo gallery or documentation thread views on Asset
- `is_technical_library` field on `File` (placeholder, no logic yet)
- Any app beyond `events/` and `assets/` referencing ActivityThread
