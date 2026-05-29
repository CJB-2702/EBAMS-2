# Phase 2 — Integration Plan

## Prerequisites

- Phase 1 complete (clean class names: `Comment`, `Attachment`, `File`)
- Dev server stopped

## Steps

1. **Update `Attachment` model** (`app/events/models/attachment.py`):
   - Add `event = ForeignKey("events.Event", on_delete=CASCADE, related_name="attachments")`
   - Change `comment` to `null=True, blank=True, on_delete=SET_NULL`
   - Add indexes on `(event, created_at)` and `(comment,)`

2. **DB reset** (new column + nullability change):
   ```bash
   python dev_tools/delete_database_rebuild_models.py --seed
   ```

3. **Update `FileHandler.upload()`** — add `event` required argument, `comment` becomes
   optional. See `control_changes.md`.

4. **Update `CommentContext.delete()`** — remove orphan-file check, replace with
   `update(comment=None)` demotion. See `control_changes.md`.

5. **Update `EventContext`** — update attachment query to fetch all attachments by
   `event_id` and partition in Python.

6. **Add cross-comment integrity check** in the control layer write path for
   comment-linked attachments.

7. **Verify**:
   ```bash
   python manage.py check
   python manage.py runserver
   ```
   Test: upload a file directly to an event (no comment). Confirm it appears standalone.
   Test: delete a comment with an attachment. Confirm the attachment demotes to
   standalone rather than disappearing.

## What will remain broken

Presentation layer — expected, repaired in Phase 4.

## What to avoid

Do not introduce `ActivityThread`, `thread_type`, `allow_comments`, or any proxy model
concept during this phase. If a PR or diff contains any reference to `ActivityThread`,
it belongs in Phase 3, not here.

## Rollback

`python dev_tools/delete_database_rebuild_models.py` and revert model file. No data to
preserve in dev.
