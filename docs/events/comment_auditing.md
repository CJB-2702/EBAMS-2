---
type: "Domain Doc"
title: "Comment Auditing — History, Attachments, and File Lifecycle"
description: "Authoritative design — source of truth for comment editing, deletion, and file cleanup."
tags: [events, domain-doc]
context_tier: 2
---

# Comment Auditing — History, Attachments, and File Lifecycle

Authoritative design — source of truth for comment editing, deletion, and file cleanup. References: [event_context_design.md](event_context_design.md), [events_endpoints.md](events_endpoints.md).

---

## 1. Data model

| Model | Mixin | `deleted_at` | `origin_id` / `revision` | PK type |
| :--- | :--- | :--- | :--- | :--- |
| `Event` | `AuditFieldsMixin` + `SoftDeleteMixin` | Yes | No | Integer |
| `EventComment` | `TraceableHistoryMixin` | Yes | Yes | Integer |
| `CommentAttachment` | `AuditFieldsMixin` + `SoftDeleteMixin` | Yes | No | UUID7 |
| `EventFile` | `AuditFieldsMixin` + `SoftDeleteMixin` | Yes | No | UUID7 |

Every content row in the events domain is soft-deletable. `CommentAttachment` is not a structural join table — it carries display state (`display_order`, `caption`, `attachment_type`) and is part of the audit trail, so it follows the same pattern.

**FK constraints on `CommentAttachment`:**

| FK | `on_delete` | Meaning |
| :--- | :--- | :--- |
| `comment` | `CASCADE` | Hard-deletes the attachment row if the comment is hard-deleted. Never fires in normal operation — comments are always soft-deleted. |
| `file` | `PROTECT` | Prevents hard-deleting a file row while any attachment row (including soft-deleted ones) still references it. Preserves referential integrity in the historical record. |

---

## 2. The invariant all operations must preserve

> **After any operation, a file has at most one active `CommentAttachment` row — the one belonging to the current (active) revision of its comment.**

Active means `deleted_at IS NULL` on both the attachment row and its comment. Soft-deleted attachment rows are historical record only.

Orphan detection is a single filter:

```python
still_referenced = CommentAttachment.objects.filter(
    file_id=file_id,
    deleted_at__isnull=True,
).exists()
```

No JOINs, no traversal through comment state.

---

## 3. Edit comment — creating a new revision

`CommentHandler.edit()` soft-deletes the old revision's attachment rows before creating the new revision's rows. The same `EventFile` rows are shared across revisions — only the attachment links change.

```
Before edit:
  Comment Rev1 (active)
    └── CommentAttachment A1 (active) → EventFile_X
    └── CommentAttachment A2 (active) → EventFile_Y

After edit:
  Comment Rev1 (deleted_at set)
    └── CommentAttachment A1 (deleted_at set) → EventFile_X   ← historical record
    └── CommentAttachment A2 (deleted_at set) → EventFile_Y   ← historical record

  Comment Rev2 (active, origin_id = Rev1)
    └── CommentAttachment A3 (active) → EventFile_X           ← new active link
    └── CommentAttachment A4 (active) → EventFile_Y           ← new active link
```

The files are unchanged. Their active reference count stays at one. No orphan check is needed on edit unless the user drops a file: then the file's orphan check fires after the old revision's attachment row is soft-deleted.

**Adding a file during edit:** `FileHandler.upload()` creates a new `EventFile` and a new `CommentAttachment` on the new comment. The old revision's attachment rows remain soft-deleted as history.

**Removing a file during edit:** the file is simply not carried forward. After the old revision's attachment row is soft-deleted, the orphan check fires for that file.

---

## 4. Delete comment

`CommentContext.delete()` soft-deletes the comment row, then soft-deletes all active attachment rows for that comment, then checks each file for orphan status.

```
CommentContext.delete():
  1. comment._soft_delete(actor)

  2. For each attachment in self.struct.attachments:
       attachment._soft_delete(actor)

       still_referenced = CommentAttachment.objects.filter(
           file_id=attachment.file_id,
           deleted_at__isnull=True,
       ).exists()

       if not still_referenced:
           FileHandler(actor).soft_delete(attachment.file)
```

If another comment still has an active attachment row pointing to the same file, the file is left alone.

---

## 5. Delete event

`EventContext.delete()` delegates to `CommentContext.delete()` for each child comment. The event itself is soft-deleted first.

```
EventContext.delete():
  1. event._soft_delete(actor)

  2. For each comment_struct in self.struct.comments:
       CommentContext.create_from_struct(comment_struct, actor).delete()
         → comment._soft_delete(actor)
         → attachment rows soft-deleted
         → orphaned files soft-deleted
```

`EventContext` does not import or reference attachment or file models directly. All child cleanup is encapsulated in `CommentContext`.

---

## 6. Explicit file delete

When the user deletes a file directly via the file delete endpoint, `FileHandler.soft_delete()` bulk-soft-deletes all attachment rows for that file, then soft-deletes the file row.

```
FileHandler.soft_delete(event_file):
  1. now = timezone.now()
     CommentAttachment.objects.filter(file=event_file).update(
         deleted_at=now,
         updated_by=actor,
         updated_at=now,
     )

  2. event_file._soft_delete(actor)
```

`update()` is used rather than iterating individual `_soft_delete()` calls — attachment rows carry no business logic that requires per-row Python execution.

**This path is intentionally unconditional.** The user has explicitly chosen to delete this file. No orphan check is performed. The `PROTECT` FK constraint on `CommentAttachment.file` is not violated because the attachment rows are soft-deleted (the rows still exist).

This differs from the cascade inside `CommentContext.delete()`, which soft-deletes attachment rows and then conditionally soft-deletes files only when they become orphaned. The two paths have different intent and must not be conflated.

---

## 7. Querying — active vs. historical views

**Active comment with its files:**

```python
comment = EventComment.objects.filter(deleted_at__isnull=True).get(pk=comment_id)
attachments = CommentAttachment.objects.filter(
    comment=comment,
    deleted_at__isnull=True,
    file__deleted_at__isnull=True,
).select_related("file")
```

**Full revision history for a comment chain:** walk back through `origin_id`, or query all revisions sharing the same chain.

**All files ever attached to any revision of a comment chain:** query attachments without filtering `deleted_at` and `.distinct("file_id")`.

**Check if a file is orphaned:** `not CommentAttachment.objects.filter(file=the_file, deleted_at__isnull=True).exists()`.

---

## 8. Operation summary

| Operation | Comment row | Attachment rows | File rows |
| :--- | :--- | :--- | :--- |
| **Edit** | Old → soft-deleted. New → created. | Old → soft-deleted. New → created (same `EventFile` FK). | Unchanged. |
| **Edit, file removed** | Old → soft-deleted. New → created. | Old → soft-deleted. No new row for removed file. | Orphan check → soft-deleted if no other active refs. |
| **Delete comment** | Soft-deleted. | All active → soft-deleted. | Per-file orphan check → soft-deleted if no other active refs. |
| **Delete event** | Soft-deleted. | All active on all child comments → soft-deleted. | Per-file orphan check via each `CommentContext.delete()`. |
| **Explicit file delete** | Unchanged. | All (active and soft-deleted) → bulk soft-deleted. | Soft-deleted unconditionally. |
| **View active state** | `deleted_at__isnull=True` | `deleted_at__isnull=True` + `file__deleted_at__isnull=True` | `deleted_at__isnull=True` |
| **Reconstruct revision N** | No filter on `deleted_at` | `comment=rev_n_comment`, no filter on `deleted_at` | Follow FK from attachment rows. |
