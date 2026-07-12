---
type: "Technical Decision"
title: "Architecture Decisions — Activity Thread Migration"
description: "Living document."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project]
context_tier: 2
---

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

## D-009 · Event → ActivityThread relationship — Django multi-table inheritance (MTI) ⚠️ SUPERSEDED

**SUPERSEDED by D-012.** Recorded here only as a rejection record.

**Rejected decision:** `Event` inherits from `ActivityThread` using Django's multi-table
inheritance. A separate `activity_thread` table holds the shared thread columns; `Event`
subclasses it and adds its own table. `activitythread_ptr_id` becomes Event's PK.

**Why this was rejected:**
- Every `Event.objects.get/filter` issues an implicit JOIN across two tables for three
  thread columns (`thread_type`, `allow_comments`, `allow_direct_attachments`).
- ~90% of rows in the activity_thread table would be Events — the thread table exists
  almost entirely to serve Event reads, making it nearly redundant.
- MTI implies ActivityThread is the parent/base and Event extends it. This is the
  **wrong conceptual direction.** Event is the primary entity. ActivityThread is a
  restricted view of Event, not its base class.

**See D-012 for the accepted design.**

---

## D-010 · EventDetailStruct assembles CommentStructs internally

**Decision:** `EventContext.load()` constructs `CommentStruct` objects using the existing
`CommentStruct.from_components()` factory and returns them inside `EventDetailStruct.comment_structs`.
Thread-level attachments (no comment) are returned separately in `unlinked_attachments`.

`ActivityThreadStruct` is an exact alias of `EventDetailStruct` — there is no separate
struct class for threads. ActivityThread rows and Event rows produce the same struct.

**Rationale:** Reuses all existing CommentStruct functionality (to_dict, revision chain,
attachment nesting) without modification. The 3-query assembly (thread + comments +
attachments) keeps the query count flat regardless of thread size. The struct alias
reinforces that **ActivityThread is a restricted proxy of Event, not a separate concept.**

**Query pattern:**
1. `Event.threads.get(pk=id)` — unfiltered, resolves any row type by id
2. `Comment.objects.filter(activity_thread_id=id, deleted_at__isnull=True)`
3. `Attachment.objects.filter(thread_id=id, deleted_at__isnull=True).select_related("file")`

Partition step 3 in Python → build CommentStructs from `from_components()`.

---

## D-011 · EventContext is the base context; ActivityThreadContext is a thin alias

**Decision:** `EventContext` owns all thread operations (comments, attachments, file
uploads, create/edit/delete). `ActivityThreadContext` inherits from `EventContext` with no
additions — it is a thin alias, not a base class.

**CRITICAL — direction of inheritance:**

```
EventContext          ← base, owns all operations
    │
    └── ActivityThreadContext   ← restricted alias, adds nothing
```

This mirrors the model layer exactly:

```
Event                 ← concrete model, physical table owner
    │
    └── ActivityThread         ← restricted proxy alias, non-event rows only
```

**ActivityThread is a restricted proxy of Event. Event is NOT a subclass of ActivityThread.**
This direction must be preserved. Any future divergence (asset-thread-specific guards,
overrides) belongs as targeted method overrides on `ActivityThreadContext`, never as new
base-class logic that `EventContext` inherits upward.

**Rationale:** Eliminates the prior inversion where `ActivityThreadContext` was the base
and `EventContext` extended it, implying threads were the primary concept. Events are the
primary entity. Threads are a restricted view of events. The context hierarchy must
reflect that.

---

## D-012 · Single table, ActivityThread is a restricted proxy of Event ← ACTIVE DESIGN

**Decision:** Event and ActivityThread share a single physical table named `event`. `Event`
is the concrete Django model. `ActivityThread` is a **restricted proxy alias** of `Event`.

**CRITICAL — the direction of this relationship:**

> **ActivityThread is a restricted proxy of Event.**
> Event is NOT a subclass of ActivityThread.
> ActivityThread IS an Event — the same row, the same table, the same `id` — viewed through
> a restricted lens (non-event rows only, event-specific fields deferred on query).

This is the opposite of the MTI design (D-009, rejected). In MTI, ActivityThread was the
parent and Event subclassed it. That direction was wrong. Events are the primary entity;
threads are a restricted view of them.

**What the proxy restricts:**
- `ActivityThread.objects` excludes event rows (`thread_type = EVENT`).
- `ActivityThread.objects` defers event-specific fields (`title`, `description`,
  `event_type`, `status`, `priority`, `event_start`, `event_end`) from the default SELECT.
- `ActivityThread.save()` auto-fills deferred fields with sentinel `"__thread__"` so
  Event's non-nullable constraints are satisfied on non-event rows.

**What the proxy does NOT add:** No new fields, no new capabilities. The proxy only
restricts and guards. All functionality lives on `Event` and `EventContext`.

**Control layer mirrors this exactly:**
- `EventContext` is the base — owns all thread operations.
- `ActivityThreadContext(EventContext)` is a thin alias — inherits everything, adds nothing.
- `ActivityThreadStruct = EventDetailStruct` — exact alias, no separate struct.

**Managers:**

| Manager | Via | Returns | Allowed in |
|---|---|---|---|
| `EventManager` | `Event.objects` | event rows only | templates, entrypoints, EventContext |
| `AssetThreadManager` | `ActivityThread.objects` | non-event rows, event fields deferred | asset entrypoints, AssetHandler |
| `AnyThreadManager` | `Event.threads` | all rows, no filter | EventContext internals only |

**PK:** Explicit `id = BigAutoField(primary_key=True)` on `Event`. One PK space, one table,
zero JOINs. `event.id == activity_thread.id` is trivially true — they are the same row.

**Supersedes:** D-009 (MTI, rejected).

---

## D-013 · Comment deletion cascades soft-delete to attachments ← SUPERSEDES D-003 (on-delete behaviour)

**Decision:** When a `Comment` is soft-deleted, all of its `Attachment` rows are also
soft-deleted in the same control-layer operation. Attachments are **not** demoted to
thread-level standalone; they are removed from the visible timeline entirely.

**How:** The cascade is enforced in the control layer (inside `CommentContext.delete()`),
not at the DB `ON DELETE` level. Both `Comment` (via `TraceableHistoryMixin`) and
`Attachment` (via `SoftDeleteMixin`) already carry `deleted_at`. The struct query filters
`deleted_at__isnull=True` so deleted rows never reach the UI.

**UI contract:** Templates render attachment lists from structs only. A struct is always
assembled with `deleted_at__isnull=True` filters, so deleted attachments are invisible
without any template-level guard.

**Supersedes D-003 (on-delete behaviour):** D-003 specified `SET_NULL` demotion
(attachment survives, `comment_id` cleared). That behaviour is replaced by soft-delete
cascade. The `comment` FK on `Attachment` remains nullable (still needed for Phase 2
standalone-attachment use case), but on comment deletion the attachment is soft-deleted,
not demoted.

---

## D-014 · Comment soft-delete pattern — TraceableHistoryMixin confirmed

**Decision:** No new mixin is needed. `Comment` (renamed from `EventComment`) already
uses `TraceableHistoryMixin`, which provides `deleted_at`, `revision`, and `origin_id`.
The `_soft_delete(actor)` method is already implemented directly on the class.

**Confirmed fields:**
- `deleted_at` — soft-delete timestamp (NULL = active)
- `revision` — integer revision counter for the edit chain
- `origin_id` — FK to self, links revision chain back to the original comment row

`Attachment` uses `SoftDeleteMixin` (provides `deleted_at` only) plus `AuditFieldsMixin`.
Both models are fully equipped for the soft-delete cascade in D-013.

---

## D-015 · Attachment composite index deferred

**Decision:** No composite index on `Attachment(thread, comment)` for now. Single-column
indexes on `thread_id` and `comment_id` are sufficient until benchmarks show otherwise.

**Rationale:** Premature optimisation. The access pattern (load all thread attachments,
partition by comment in Python) can be proven or disproven under real data before
committing to a custom index.

---

## D-016 · File.checksum_sha256 included from the start

**Decision:** `checksum_sha256 = CharField(max_length=64, blank=True)` is included on
the `File` model from Phase 1 (as a rename target from `EventFile`). Populated
opportunistically on upload; blank is valid.

**Rationale:** Cheap to add at schema creation time. Useful for deduplication and
integrity checks even before a formal dedup feature exists. Deferring costs a migration
later for a trivially small column.
