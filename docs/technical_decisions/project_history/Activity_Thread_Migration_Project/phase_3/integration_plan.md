# Phase 3 — Integration Plan

## Prerequisites

- Phase 2 complete (`Attachment` has direct `event` FK, `comment` FK is nullable)
- Dev server stopped

## Steps

1. **Add `ActivityThreadType` enum and new managers to `event.py`**

2. **Add new columns to `Event` model**:
   - `thread_type` (CharField, db_index=True)
   - `allow_comments` (BooleanField, default=True)
   - `allow_direct_attachments` (BooleanField, default=True)
   - Make `status` and `priority` nullable

3. **Add `ActivityThread` proxy class to `event.py`**

4. **Update `Event` manager assignments**:
   - `objects = EventManager()` (now filters to event rows only)
   - `threads = AnyThreadManager()` (unfiltered escape hatch)

5. **Update `Comment` model** (`comment.py`):
   - Rename `event` FK → `activity_thread`
   - Change target from `"events.Event"` to `"events.ActivityThread"`
   - DB column renames from `event_id` → `activity_thread_id`

6. **Update `Attachment` model** (`attachment.py`):
   - Rename `event` FK → `thread`
   - Change target from `"events.Event"` to `"events.ActivityThread"`
   - DB column renames from `event_id` → `thread_id`

7. **Update `Asset` model**:
   - Add `photo_gallery = OneToOneField("events.ActivityThread", PROTECT, related_name="photo_gallery_asset")`
   - Add `documentation = OneToOneField("events.ActivityThread", PROTECT, related_name="documentation_asset")`

8. **DB reset**:
   ```bash
   python dev_tools/delete_database_rebuild_models.py --seed
   ```

9. **Create `ActivityThreadContext`** in `activity_thread_context.py` (thin alias).

10. **Update `EventContext`**:
    - `row` property uses `Event.threads.get(pk=...)`
    - `create_new()` writes `thread_type=ActivityThreadType.EVENT`

11. **Update handlers** — FK field name changes (`event` → `thread`, `event` → `activity_thread`).

12. **Update structs** — add `thread_type`, `allow_comments`, `allow_direct_attachments` fields.

13. **Update `__init__.py`** — add `ActivityThread`, `ActivityThreadType` exports.

14. **Update `AssetHandler.create()`** — atomic thread pair creation.

15. **Verify**:
    ```bash
    python manage.py check
    python manage.py runserver
    ```
    Test: create an event — confirm `Event.objects` returns it, `ActivityThread.objects` does not.
    Test: create an asset — confirm two `ActivityThread` rows are created atomically.
    Test: add a comment to an event — confirm `comment.activity_thread_id` is set.
    Test: attach a file to an event — confirm `attachment.thread_id` is set.

## What will remain broken

Presentation layer — expected, repaired in Phase 4.
