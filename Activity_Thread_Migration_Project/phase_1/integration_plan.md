# Phase 1 — Integration Plan

## Prerequisites

- No active DB migrations to preserve
- Dev server stopped

## Steps

1. **Rename model files** (optional but keeps paths clean):
   - `comment.py` — keep path, rename class inside
   - `attachment.py` — keep path, rename class inside
   - `file.py` — keep path, rename class inside

2. **Apply model class renames** inside each file:
   - Update `class EventComment` → `class Comment`
   - Update `Meta.db_table` on each model to new table name
   - Update `EventCommentQuerySet` / `EventCommentManager` etc.
   - Update any self-references inside the file (e.g. `EventFile.is_allowed_extension()` stays but class name changes)

3. **Update `app/events/models/__init__.py`** with new export names.

4. **Update domain structs**:
   - Rename `base_event_struct.py` → `event_detail_struct.py` (and class inside)
   - Rename `base_event_super_struct.py` → `event_super_struct.py` (and class inside)
   - Update `domain_structs/__init__.py`

5. **Update control layer handlers and contexts** (see `control_changes.md`).

6. **Update cross-app references**:
   - `app/assets/models/core/asset_image.py` — update any imports of old names

7. **DB reset**:
   ```bash
   python dev_tools/delete_database_rebuild_models.py --seed
   ```
   Table renames require a full reset.

8. **Verify**:
   ```bash
   python manage.py check
   python manage.py runserver
   ```

## What will be broken after Phase 1

Presentation layer files (`entrypoints/`, `search/`, `tools/`, `admin.py`) may have
broken imports. This is expected and will be repaired in Phase 4. The control layer and
model layer should be clean.

## Rollback

If something goes wrong: `python dev_tools/delete_database_rebuild_models.py` and
revert the renamed files. There is no data to preserve in dev.
