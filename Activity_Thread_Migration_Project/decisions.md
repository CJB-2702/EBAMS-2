# Architecture Decisions — Activity Thread Migration

Living document. Append new decisions as they are made. Most recent decisions at the bottom.
For full context see `Domain_Changes.md` and `control_layer_services.md`.

---

## D-001 · ActivityThread app location

**Decision:** ActivityThread model lives in `app/events/`, re-exported from `events.models`.
All other apps (`assets/`, future apps) import from `events.models`.

**Rationale:** Avoids creating a new shared-infrastructure app for a single model.
The events app is already the natural owner of comments, files, and attachments.
All apps will "use events" as the activity layer for the most part with notable exceptions where the exceptions are the driving reason behind this refactor.

**Consequences:** If ActivityThread ever needs to be imported by an app that cannot
import from events (circular dependency), this will need revisiting.

---

## D-002 · Thread behavioral flags — explicit over derived

**Decision:** ActivityThread behavior is controlled by two explicit boolean flags rather
than being derived from `thread_type`. The two flags are:

- `allow_comments: bool` — controls whether human comments may be written to this thread.
- `allow_direct_attachments: bool` — controls whether files may be attached directly to the
  thread without being associated with a comment.

`thread_type` (the enum) is retained as a label for display and filtering but does **not**
drive any service-layer logic. All behavioral gates check the flags only.

**Conventions by thread purpose:**
- Event thread → `allow_comments=True`, `allow_direct_attachments=True`
- Photo gallery → `allow_comments=False`, `allow_direct_attachments=True`
- Documentation → `allow_comments=True`, `allow_direct_attachments=True`

**Deferred:** An explicit `table_thread_for` (or similar) column to record which entity
type owns the thread. Useful for admin queries and future cross-domain lookups. Not needed
for the current implementation — deferred to avoid premature design.

**Rationale:** Using flags avoids coupling behavior to the type enum. A future thread
purpose can be introduced with any combination of flags without adding enum cases and
branching logic. The two flags map to two distinct UI affordances that can be toggled
independently.

---

## D-003 · Attachment — single model consolidating two prior classes

**Decision:** A single `Attachment` model replaces what would have been two separate classes
(`CommentAttachment` for comment-linked files, a hypothetical `DirectAttachment` for
thread-level files). One model handles both cases via a nullable `comment_id`.

- `thread_id` — mandatory FK to ActivityThread. Every attachment belongs to a thread.
- `comment_id` — nullable FK to Comment (SET_NULL, not CASCADE). When set, the attachment
  appears nested under that comment in the timeline. When NULL, it appears as a standalone
  thread-level file.

**Rationale:** Two separate models would duplicate the file-to-thread linkage and require
branching query logic everywhere. One model with an optional comment association consolidates
both use cases into a single indexed table. The display-layer distinction (nested vs.
standalone) is handled by partitioning in Python after a single query, not by model type.

**Service invariant:** When inserting an Attachment with a non-null comment, the context
must verify `comment.activity_thread_id == attachment.thread_id` before writing.
The DB cannot enforce this cross-table check cheaply.

**On comment deletion:** `comment_id` is cleared to NULL (demotes to thread-level).
The file is NOT soft-deleted and NOT considered orphaned. The orphan-file check from the old
`CommentContext.delete()` is removed entirely.

---

## D-004 · Comment parent FK

**Decision:** `Comment.activity_thread` FK replaces `Comment.event` FK.

**Rationale:** Comments belong to a thread, not to a specific entity type. This makes the
comment model reusable across events, assets, and any future entity that holds a thread FK.

---

## D-005 · File model — standalone, no thread FK

**Decision:** `File` (renamed from `EventFile`) has no FK to ActivityThread.
It is a pure storage record. Visibility is established only through Attachment rows.

**Rationale:** Keeps the file model generic and avoids premature coupling. A file uploaded
once could theoretically be referenced by multiple Attachment rows (e.g. carry-forward on
comment edit). If the file held a thread FK, that would break on multi-reference.

---

## D-006 · Asset thread columns — explicit named FKs

**Decision:** `Asset` gets two explicit OneToOneField columns: `photo_gallery` and
`documentation`, both pointing to `ActivityThread`.

**Rationale:** Named columns are self-documenting and prevent accidental slot-swapping.
A generic join table would allow two `photo_gallery` threads per asset; explicit columns
make that structurally impossible.

---

## D-007 · Asset thread creation — eager

**Decision:** Both asset threads are created inside the same `transaction.atomic()` block
as the Asset row itself. Threads are never created lazily on first access.

**Rationale:** Eliminates the race condition where two requests simultaneously try to create
the same thread. Templates and contexts always have a valid thread ID to work with even when
the thread is empty.

---

## D-008 · anchor_event replaced by activity_thread

**Decision:** The planned `anchor_event` FK (Event FK) on `DefinedModification`,
`CapabilityDefinition`, and `ConfigurationTemplate` is replaced with an `activity_thread`
FK (ActivityThread FK).

**Rationale:** Linking to an ActivityThread is more general — it survives if the thread
is not attached to an Event. It also keeps these models from importing from the Event model
directly, reducing coupling depth.

---

## D-009 · Event → ActivityThread relationship — Django multi-table inheritance (MTI)

**Decision:** `Event` inherits from `ActivityThread` using Django's multi-table inheritance.
There is no explicit FK or `OneToOneField` on Event — Django generates the parent-link
column (`activitythread_ptr_id`) automatically and uses it as Event's primary key.

```python
class ActivityThread(AuditFieldsMixin):
    allow_comments = ...
    allow_direct_attachments = ...

class Event(ActivityThread, SoftDeleteMixin):
    domain = ...
    title = ...
```

**Why MTI over explicit OneToOneField(primary_key=True):**
- The shared-PK guarantee (`event.pk == activity_thread.pk`) was the original goal. MTI
  delivers this automatically without any handler-level coordination.
- `Event.objects.create(allow_comments=True, title=...)` creates both rows in a single
  call — Django handles the two-row insert atomically. No two-step "create thread, then
  create event" dance in the handler.
- `event.allow_comments` and `event.allow_direct_attachments` are accessible directly as
  if they were native Event fields — no `.activity_thread.allow_comments` traversal.
- Rescue invariant preserved: `ActivityThread.objects.get(pk=n)` and
  `Event.objects.get(pk=n)` always refer to the same logical entity.

**Trade-off acknowledged:** Every `Event.objects.get/filter` issues an implicit JOIN to
`activity_thread`. This is acceptable because EventContext always needs both rows and the
JOIN cost over two small-column tables is negligible at the expected data volume.

**Asset threads are NOT subclassed.** Asset photo_gallery and documentation threads remain
plain `ActivityThread` rows — only Event uses MTI. Plain threads have no subclass overhead.

**Implementation note:** The default `id = BigAutoField` is removed from Event. Django
substitutes `activitythread_ptr_id` as the PK. Existing hashid encoding at URL boundaries
is unchanged — it still encodes `event.pk`.

---

## D-010 · ActivityThreadStruct assembles CommentStructs internally

**Decision:** `ActivityThreadContext.load()` constructs `CommentStruct` objects using the
existing `CommentStruct.from_components()` factory and returns them inside
`ActivityThreadStruct.comment_structs`. Thread-level attachments (no comment) are returned
separately in `unlinked_attachments`.

**Rationale:** Reuses all existing CommentStruct functionality (to_dict, revision chain,
attachment nesting) without modification. The 3-query assembly (thread + comments +
attachments) keeps the query count flat regardless of thread size. Callers at the
EventContext level receive fully ready structs and never need to issue follow-up queries.

**Query pattern:**
1. `ActivityThread.objects.get(pk=thread_id)`
2. `Comment.objects.filter(activity_thread_id=thread_id, deleted_at__isnull=True)`
3. `Attachment.objects.filter(thread_id=thread_id, deleted_at__isnull=True).select_related("file")`

Partition step 3 in Python → build CommentStructs from `from_components()`.

---

## D-011 · EventContext is the caller boundary

**Decision:** `EventContext` is the only class callers use to read event + thread data.
It delegates internally to `ActivityThreadContext` and maps the result onto `EventDetailStruct`
fields (`comment_structs`, `unlinked_attachments`, `can_comment`). No template or entrypoint
imports ActivityThread, ActivityThreadContext, or ActivityThreadStruct.

**Rationale:** Keeps the thread as an implementation detail. If the thread model changes
(e.g. ActivityThread moves to a different app), only EventContext and ActivityThreadContext
need updating — templates and entrypoints are untouched.
