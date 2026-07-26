---
type: "Technical Decision"
title: "Blast Radius — Activity Thread / Event Refactor"
description: "Everything in this document **requires a change** to compile and run correctly after."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project]
context_tier: 2
---

> **Superseded.** This doc treats the migration as a single phase. Blast radius is now
> distributed across the phase docs: [phase_1/](phase_1/), [phase_2/](phase_2/),
> [phase_3/](phase_3/), [phase_4/](phase_4/). Retained as cross-reference.

# Blast Radius — Activity Thread / Event Refactor

Everything in this document **requires a change** to compile and run correctly after
the migration. Grouped by impact severity.

---

## Severity legend

| Level | Meaning |
|---|---|
| 🔴 Breaking — schema | DB table/column change. Full DB reset required. |
| 🟠 Breaking — rename | Class or FK name changed. Import and reference updates required everywhere it's used. |
| 🟡 Logic change | Same class/file; internal logic must be updated. |
| 🟢 Additive | New class or column added; existing code unaffected until it adopts it. |

---

## 1. Schema changes (🔴 — DB reset required for all of these)

| Table | Change | Reason |
|---|---|---|
| `event` | Add column `thread_type VARCHAR(50) NOT NULL` with index | STI discriminator |
| `event` | Add column `allow_comments BOOLEAN NOT NULL DEFAULT TRUE` | D-002 |
| `event` | Add column `allow_direct_attachments BOOLEAN NOT NULL DEFAULT TRUE` | D-002 |
| `event` | Add explicit `id BIGINT PRIMARY KEY` | D-012 |
| `event` | `event_start` — drop NULL, make required | Events must have a start time |
| `event` | `status` — add NULL constraint (was defaulting to PLANNED, becomes nullable for non-event rows) | Sentinel pattern |
| `event_comment` | Rename table → `comment` | Rename |
| `event_comment` | Rename column `event_id` → `activity_thread_id` | D-004 |
| `event_comment_attachment` | Rename table → `attachment` | Rename / D-003 |
| `event_comment_attachment` | Add column `thread_id BIGINT NOT NULL` FK → `event.id` | D-003 mandatory thread FK |
| `event_comment_attachment` | `comment_id` — add NULL constraint (was NOT NULL) | D-003 standalone attachment |
| `event_file` | Rename table → `file` | Rename / D-005 |

> **One action covers all of these:** `python dev_tools/delete_database_rebuild_models.py --seed`

---

## 2. Model renames (🟠 — every import site must update)

These classes no longer exist under their old names. Every `import` or reference breaks.

| Old name | New name | File |
|---|---|---|
| `EventComment` | `Comment` | `app/events/models/comment.py` |
| `EventCommentQuerySet` | `CommentQuerySet` | `app/events/models/comment.py` |
| `EventCommentManager` | `CommentManager` | `app/events/models/comment.py` |
| `CommentAttachment` | `Attachment` | `app/events/models/attachment.py` |
| `CommentAttachmentQuerySet` | `AttachmentQuerySet` | `app/events/models/attachment.py` |
| `CommentAttachmentManager` | `AttachmentManager` | `app/events/models/attachment.py` |
| `EventFile` | `File` | `app/events/models/file.py` |
| `BaseEventStruct` | `EventDetailStruct` | `app/events/control_layer/domain_structs/event_detail_struct.py` |
| `BaseEventSuperStruct` | `EventSuperStruct` | `app/events/control_layer/domain_structs/event_super_struct.py` |

**Files that import these old names (every one must be updated):**

```
app/events/models/__init__.py
app/events/models/file.py                                  ← self-reference
app/events/control_layer/event_context.py
app/events/control_layer/comment_context.py
app/events/control_layer/file_context.py
app/events/control_layer/handlers/event_handler.py
app/events/control_layer/handlers/comment_handler.py
app/events/control_layer/handlers/file_handler.py
app/events/control_layer/domain_structs/base_event_struct.py
app/events/control_layer/domain_structs/base_event_super_struct.py
app/events/control_layer/domain_structs/comment_struct.py
app/events/control_layer/domain_structs/__init__.py
app/events/presentation_layer/entrypoints/events.py
app/events/presentation_layer/entrypoints/comments.py
app/events/presentation_layer/entrypoints/files.py
app/events/presentation_layer/search/event_search.py
app/events/presentation_layer/tools/file_previews.py
app/events/admin.py
app/events/migrations/0001_initial.py                      ← wiped on DB reset
app/assets/models/core/asset_image.py                      ← cross-app reference
```

---

## 3. FK target changes (🟠 — all FK definitions must be rewritten)

| Model | Field | Old target | New target |
|---|---|---|---|
| `Comment` | `activity_thread` | `"events.Event"` | `"events.ActivityThread"` |
| `Attachment` | `comment` | `"events.EventComment"` | `"events.Comment"` |
| `Attachment` | `thread` | _(did not exist)_ | `"events.ActivityThread"` (new, mandatory) |
| `Attachment` | `file` | `"events.EventFile"` | `"events.File"` |

---

## 4. `EventContext` — full rewrite (🟡 Logic change)

`EventContext` is currently a thin façade that delegates everything to handlers.
Post-migration it becomes the **base** context for all thread operations (D-011).

| Change | Detail |
|---|---|
| `__init__` signature | `event_id` → `id`; `self.struct = BaseEventStruct(event_id)` removed; lazy `row` property via `Event.threads.get(pk=id)` instead. |
| `create_from_struct()` | Replaced by `create_new(post_data, actor)` classmethod (single `Event.objects.create(thread_type=EVENT, ...)`). |
| `edit()` | Was `EventHandler(actor).edit(...)`. Becomes an inline method (or still delegates — but signature changes). |
| `add_comment()` | Was `EventHandler + EventComment.create(event=...)`. Becomes `Comment.create(activity_thread=...)`. |
| `add_attachment()` | Was "create machine comment as carrier." Post-migration direct thread attachments are first-class — no machine-comment carrier needed. |
| `delete()` | `CommentContext` cascade loop stays; model references update to `Comment`. |
| New methods added | `load() → EventDetailStruct`, `attach_file()`, `detach_attachment()`, `set_status()`. |

---

## 5. `CommentContext.delete()` — orphan logic removed (🟡 Logic change)

The orphan-file check is **deleted** (D-003):

```python
# REMOVED — this block no longer exists after migration:
still_referenced = CommentAttachment.objects.filter(
    file_id=attachment.file_id,
    deleted_at__isnull=True,
).exists()
if not still_referenced:
    FileHandler(self.actor).soft_delete(attachment.file)
```

On comment delete, `Attachment.comment` is set to NULL (demote to thread-level standalone
attachment). The file and attachment row are **not deleted**. This changes observable
behaviour — files that were comment-linked will appear as thread-level after their
comment is deleted.

---

## 6. `EventManager` — semantics change (🟡 Logic change)

The current `EventManager` returns all non-deleted rows.
Post-migration `EventManager` returns **only `thread_type=EVENT` rows**.
Any caller that previously expected `Event.objects` to return asset-thread rows will
silently get fewer results. (Currently no such callers exist — confirming this before build.)

---

## 7. `EventHandler.create()` — new required fields (🟡 Logic change)

`create()` must now also pass:
- `thread_type=ActivityThreadType.EVENT`
- `allow_comments=True` (default for events)
- `allow_direct_attachments=True` (default for events)

Any caller of `EventHandler.create()` that provides `post_data` without these keys
will still work because they get default values — but the create method must set them
explicitly so rows are correctly discriminated.

---

## 8. `FileHandler.upload()` — new `thread_id` required (🟡 Logic change)

`CommentAttachment.objects.create(comment=comment, file=..., ...)` currently requires
only `comment`. Post-migration `Attachment.objects.create(...)` requires **both**
`thread` (mandatory FK) and `comment` (optional). `FileHandler.upload()` must be
updated to accept and pass the thread context.

---

## 9. Cross-app: `app/assets/models/core/asset_image.py` (🟠 Breaking — rename)

This file currently imports from `app.events.models`. It references at minimum
`EventFile` or `CommentAttachment`. Both are renamed. This file must be updated.

Also: `Asset` model must gain two new `OneToOneField` columns (D-006):

```
photo_gallery   → OneToOneField("events.ActivityThread", on_delete=PROTECT)
documentation   → OneToOneField("events.ActivityThread", on_delete=PROTECT)
```

This is a schema change on the `asset` table — covered by the DB reset.

---

## 10. New files — must be created (🟢 Additive)

These do not exist yet and must be written from scratch:

| File | Contents |
|---|---|
| `app/events/models/event.py` (additions) | `ActivityThreadType` enum, `AssetThreadManager`, `AnyThreadManager`, `ActivityThread` proxy class |
| `app/events/control_layer/activity_thread_context.py` | `ActivityThreadContext(EventContext)` — thin alias |
| `app/events/control_layer/policies/thread_policy.py` | `ThreadPolicy` |
| `app/events/control_layer/guards/attachment_thread_guard.py` | `AttachmentThreadGuard` |
| `app/events/control_layer/domain_structs/attachment_struct.py` | `AttachmentStruct` |
| `app/events/control_layer/domain_structs/file_struct.py` | `FileStruct` |

---

## 11. Templates — conditional (🟡 — audit required before build)

Templates that render attachment lists or check `comment.event` / `attachment.comment`
attributes may require path updates. No template is known to be broken at this point
— a template audit pass is needed before declaring the migration complete.

Key patterns to search for in templates:
```
comment.event
attachment.comment_id
object.event_id
```

---

## Summary table

| Area | Files affected | Severity |
|---|---|---|
| DB schema | `event`, `comment`, `attachment`, `file` tables | 🔴 Reset |
| Model renames | 9 class renames across 5 model files | 🟠 |
| FK targets | `Comment.activity_thread`, `Attachment.thread`, `Attachment.comment` | 🟠 |
| `EventContext` rewrite | `event_context.py` | 🟡 |
| `CommentContext.delete()` | orphan check removed | 🟡 |
| `EventManager` scope | filters to EVENT rows only | 🟡 |
| `EventHandler.create()` | new required thread fields | 🟡 |
| `FileHandler.upload()` | new `thread_id` argument | 🟡 |
| Cross-app: `assets` | `asset_image.py` + `Asset` model new FK columns | 🟠 + 🔴 |
| New files | 6 new files | 🟢 |
| Templates | Audit pass required | 🟡 |
