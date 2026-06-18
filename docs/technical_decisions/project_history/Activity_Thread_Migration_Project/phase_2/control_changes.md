# Phase 2 — Control Layer Changes

---

## `FileHandler.upload()` — new `event` argument

**Before Phase 2:**
```python
def upload(self, comment: Comment, uploaded_file) -> FileResult:
    file = File.objects.create(...)
    attachment = Attachment.objects.create(
        comment=comment,
        file=file,
        ...
    )
```

**After Phase 2:**
```python
def upload(self, event: Event, uploaded_file, comment: Comment | None = None) -> FileResult:
    file = File.objects.create(...)
    attachment = Attachment.objects.create(
        event=event,
        comment=comment,   # None for standalone event attachments
        file=file,
        ...
    )
```

`event` is now a required argument. `comment` is optional — when `None`, the attachment
is standalone on the event.

---

## New: standalone attachment method

A dedicated path for attaching a file directly to an event (no comment):

```python
# In EventContext or as a standalone function:
def attach_file_to_event(event: Event, file: File, display_name: str = "") -> Attachment:
    return Attachment.objects.create(
        event=event,
        comment=None,
        file=file,
        display_name=display_name,
        ...
    )
```

---

## `CommentContext.delete()` — orphan check removed

**Before Phase 2:**
```python
def delete(self):
    for attachment in self.comment.attachments.filter(deleted_at__isnull=True):
        still_referenced = Attachment.objects.filter(
            file_id=attachment.file_id,
            deleted_at__isnull=True,
        ).exclude(pk=attachment.pk).exists()
        if not still_referenced:
            FileHandler(self.actor).soft_delete(attachment.file)
        attachment.soft_delete()
    self.comment.soft_delete()
```

**After Phase 2:**
```python
def delete(self):
    # Demote comment-linked attachments to standalone event attachments.
    # The attachment row and underlying file survive — they belong to the event.
    self.comment.attachments.filter(deleted_at__isnull=True).update(comment=None)
    self.comment.soft_delete()
```

The orphan-file check is removed. Files are never deleted as a side effect of comment
deletion. Attachments are demoted (comment FK → NULL) and remain visible on the event.

---

## `EventContext` — new query path for standalone attachments

`EventContext.load()` (or wherever the event detail struct is assembled) must now fetch
both comment-linked and standalone attachments:

```python
# All attachments for the event:
all_attachments = Attachment.objects.filter(
    event_id=self._id,
    deleted_at__isnull=True,
).select_related("file")

# Split in Python:
comment_attachments = [a for a in all_attachments if a.comment_id is not None]
standalone_attachments = [a for a in all_attachments if a.comment_id is None]
```

Partition in Python after a single query — do not issue separate queries for each set.

---

## Cross-comment integrity check

When creating an `Attachment` with a non-null `comment`, verify:

```python
if comment is not None and comment.event_id != event.id:
    raise ValueError("Comment does not belong to this event.")
```

This check belongs in the control layer write path, not in the model.

---

## What does NOT change in Phase 2

- `Comment` model and its handlers — no changes
- `Event` model — no changes
- `File` model — no changes
- Struct field shapes (`to_dict()` output) — gains `event_id` and `comment_id` is now
  nullable in output, but no field is removed
- `EventContext.add_comment()` — no changes
- `EventContext.edit()` / `delete()` — no changes (other than the cascade onto
  Attachment via `event` FK which DB handles automatically)

---

## Note: no ActivityThread anywhere

All control layer code in Phase 2 works with `Event` directly. The `event` parameter
name is used throughout. Do not use `thread`, `activity_thread`, or any ActivityThread
terminology in Phase 2 code.
