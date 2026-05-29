# Phase 1 — Control Layer Changes

All changes are import and reference updates. No method signatures change. No business
logic changes.

---

## Domain struct renames

| Old name | New name | File |
|---|---|---|
| `BaseEventStruct` | `EventDetailStruct` | `app/events/control_layer/domain_structs/event_detail_struct.py` |
| `BaseEventSuperStruct` | `EventSuperStruct` | `app/events/control_layer/domain_structs/event_super_struct.py` |

File should be renamed to match the new class name. The `_build_comment_structs()`,
`from_components()`, and `to_dict()` methods are unchanged.

---

## Files that need import and reference updates

Every reference to the old class names must be replaced with the new names.

```
app/events/models/__init__.py
app/events/models/file.py                   (self-reference EventFile → File)
app/events/control_layer/event_context.py
app/events/control_layer/comment_context.py
app/events/control_layer/file_context.py
app/events/control_layer/handlers/event_handler.py
app/events/control_layer/handlers/comment_handler.py
app/events/control_layer/handlers/file_handler.py
app/events/control_layer/domain_structs/__init__.py
app/events/control_layer/domain_structs/comment_struct.py
app/events/presentation_layer/entrypoints/events.py      (presentation — will break; fixed in Phase 4)
app/events/presentation_layer/entrypoints/comments.py    (presentation — will break; fixed in Phase 4)
app/events/presentation_layer/entrypoints/files.py       (presentation — will break; fixed in Phase 4)
app/events/presentation_layer/search/event_search.py     (presentation — will break; fixed in Phase 4)
app/events/presentation_layer/tools/file_previews.py     (presentation — will break; fixed in Phase 4)
app/events/admin.py                                       (presentation — will break; fixed in Phase 4)
app/assets/models/core/asset_image.py                    (cross-app reference)
```

Presentation layer files are listed for completeness. They are deliberately left broken
and repaired in Phase 4.

---

## Handler reference updates

### `event_handler.py`

- `EventComment.objects.create(...)` → `Comment.objects.create(...)`
- `CommentAttachment` → `Attachment` everywhere
- `EventFile` → `File` everywhere
- Logic is unchanged.

### `comment_handler.py`

- `EventComment` → `Comment`
- `CommentAttachment` → `Attachment`
- `EventFile` → `File`
- `old_comment.event` field access — field name on the model stays `event` (no rename yet)
- Logic is unchanged.

### `file_handler.py`

- `EventFile` → `File`
- `CommentAttachment` → `Attachment`
- Logic is unchanged. `upload(comment, uploaded_file)` signature unchanged.

---

## Context reference updates

### `event_context.py`

- `BaseEventStruct` → `EventDetailStruct`
- `EventComment` → `Comment`
- `CommentAttachment` → `Attachment`
- `EventFile` → `File`
- Logic unchanged.

### `comment_context.py`

- `EventComment` → `Comment`
- `CommentAttachment` → `Attachment`
- `EventFile` → `File`
- The `event` property still fetches an `Event` row via `comment.event_id` — no change.

### `file_context.py`

- `EventFile` → `File`

---

## What does NOT change in Phase 1

- Method signatures
- FK field names on models (`comment.event_id` stays `event_id`)
- Business logic in any method
- Query patterns
- Struct field names in `to_dict()` output
