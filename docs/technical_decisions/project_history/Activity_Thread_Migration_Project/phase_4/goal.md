# Phase 4 — Goal: Presentation Layer Repair

## Problem

Phases 1–3 deliberately allow the presentation layer to break. By the end of Phase 3:

- Entrypoints reference old class names (`EventComment`, `CommentAttachment`, `EventFile`,
  `BaseEventStruct`)
- Search classes reference old model names and missing `thread_type` filters
- Admin registrations use old model names
- Templates may reference old field paths (`comment.event`, `attachment.comment_id` as
  a required field, `object.event_id`)
- `file_previews.py` references `EventFile`

## What this phase does

Systematic pass through the entire presentation layer to fix every broken reference.
No model changes. No control layer changes.

## Scope

```
app/events/presentation_layer/entrypoints/events.py
app/events/presentation_layer/entrypoints/comments.py
app/events/presentation_layer/entrypoints/files.py
app/events/presentation_layer/search/event_search.py
app/events/presentation_layer/tools/file_previews.py
app/events/admin.py
app/events/templates/          (audit for old field paths)
app/assets/presentation_layer/ (if any cross-app templates reference event fields)
```

## What this phase does NOT do

- No model changes
- No control layer changes
- No new features

## Success criteria

- `python manage.py check` reports no errors
- All presentation layer files import cleanly
- `python manage.py runserver` starts without error
- All major event and asset pages load and render correctly
- File upload, comment add, attachment display all work end-to-end
