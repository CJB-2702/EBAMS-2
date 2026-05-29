# Phase 4 — Integration Plan

## Prerequisites

- Phases 1, 2, and 3 complete
- DB reset has been run after Phase 3

## Audit and fix — entrypoints

For each file in `presentation_layer/entrypoints/`:

- Replace `EventComment` → `Comment`
- Replace `CommentAttachment` → `Attachment`
- Replace `EventFile` → `File`
- Replace `BaseEventStruct` → `EventDetailStruct`
- Replace `BaseEventSuperStruct` → `EventSuperStruct`
- Update any reference to `comment.event_id` → `comment.activity_thread_id`
- Update any reference to `attachment.comment_id` (now nullable — guard any required
  access)

## Audit and fix — search

`event_search.py`:
- Ensure queries filter on `thread_type=ActivityThreadType.EVENT` (or rely on
  `Event.objects` which already does this via `EventManager`)
- Replace any old model name references

## Audit and fix — tools

`file_previews.py`:
- Replace `EventFile` → `File`
- Extension / MIME helpers are unchanged, just import path updates

## Audit and fix — admin

`admin.py`:
- Replace `EventComment` → `Comment`
- Replace `CommentAttachment` → `Attachment`
- Replace `EventFile` → `File`
- Re-register models under new names

## Template audit

Search for these patterns across `app/events/templates/` and any asset templates:

```
comment.event
attachment.comment_id   (now nullable — conditional access required)
object.event_id
event.eventcomment_set  (old reverse accessor — now event.comments)
```

Update to:
- `comment.activity_thread` / `comment.activity_thread_id`
- `{% if attachment.comment %}` guards where needed
- `event.comments.all()` (reverse accessor via new related_name)

## Verify

```bash
python manage.py check
python manage.py runserver
```

Manual smoke test:
1. Event list page loads
2. Event detail page loads (comments + attachments visible)
3. Add a comment — submits and appears
4. Upload a file to an event directly (no comment) — appears as standalone attachment
5. Upload a file attached to a comment — appears nested under comment
6. Delete a comment with an attachment — attachment demotes to standalone (does not disappear)
7. Asset detail page loads with photo gallery and documentation threads visible
