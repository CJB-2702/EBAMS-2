---
type: "Technical Decision"
title: "Things to Keep — Activity Thread / Event Refactor"
description: "Everything in this document **survives the migration**."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project]
context_tier: 2
---

> **Superseded.** This doc treats the migration as a single phase. The "keep vs. change"
> breakdown is now distributed across the phase docs. Retained as cross-reference for
> what survives each phase.

# Things to Keep — Activity Thread / Event Refactor

Everything in this document **survives the migration**. Some items keep their file path
and class name unchanged; others require implementation edits but the class/concept stays.
Nothing here is deleted; everything here has an end-state home.

---

## Legend

| Symbol | Meaning |
|---|---|
| ✅ Unchanged | File, class name, and implementation survive as-is. |
| ✏️ Rename only | Class/file is renamed; logic is the same. |
| 🔧 Implementation changes | Class survives; internal references or method signatures need updating. |

---

## Models

### `app/events/models/event.py`

| Class / Symbol | Status | Notes |
|---|---|---|
| `EventType(TextChoices)` | ✅ Unchanged | All existing choices stay. |
| `EventStatus(TextChoices)` | ✅ Unchanged | All existing choices stay. |
| `EventPriority(TextChoices)` | ✅ Unchanged | All existing choices stay. |
| `PRIORITY_CLEARING_STATUSES` | ✅ Unchanged | Same set of statuses. |
| `EventQuerySet` | 🔧 Implementation changes | `.visible_to()` stays. Must now filter on `thread_type=EVENT` so it never returns asset-thread rows. |
| `Event` (model class) | 🔧 Implementation changes | New columns added (`thread_type`, `allow_comments`, `allow_direct_attachments`). `event_start` becomes non-nullable. `status`/`priority` become nullable. Explicit `id = BigAutoField(primary_key=True)`. `Meta.db_table = "event"` stays. |
| `Event._soft_delete()` | ✅ Unchanged | Same pattern. |

### `app/events/models/comment.py`

| Class / Symbol | Status | Notes |
|---|---|---|
| `EventComment` | ✏️ Rename only → `Comment` | All columns stay. `db_table` changes from `"event_comment"` to `"comment"`. The `event` FK column is **renamed** to `activity_thread` and points to `"events.ActivityThread"` instead of `"events.Event"`. |
| `EventCommentQuerySet` | ✏️ Rename only → `CommentQuerySet` | `.active()`, `.human()`, `.shadow()`, `.current_revisions()` all stay. |
| `EventCommentManager` | ✏️ Rename only → `CommentManager` | Same logic. |
| `Comment._soft_delete()` | ✅ Unchanged | Same pattern. |
| `revision` / `origin_id` / `is_human_made` columns | ✅ Unchanged | Revision chain pattern stays intact. |

### `app/events/models/attachment.py`

| Class / Symbol | Status | Notes |
|---|---|---|
| `AttachmentType(TextChoices)` | ✅ Unchanged | IMAGE, DOCUMENT, VIDEO stay. |
| `CommentAttachment` | ✏️ Rename only → `Attachment` | UUID PK stays. Gains direct `thread` FK (mandatory). `comment` FK target changes from `EventComment` to `Comment`. `db_table` changes from `"event_comment_attachment"` to `"attachment"`. `caption` and `display_order` columns stay. |
| `CommentAttachmentQuerySet` | ✏️ Rename only → `AttachmentQuerySet` | `.active()` stays. |
| `CommentAttachmentManager` | ✏️ Rename only → `AttachmentManager` | Same logic. |
| `Attachment._soft_delete()` | ✅ Unchanged | Same pattern. |

### `app/events/models/file.py`

| Class / Symbol | Status | Notes |
|---|---|---|
| `ALLOWED_EXTENSIONS` | ✅ Unchanged | Same extension map. |
| `TEXT_PREVIEW_EXTENSIONS` | ✅ Unchanged | Same set. |
| `_ICON_MAP` | ✅ Unchanged | Same mapping. |
| `MAX_FILE_SIZE_BYTES` | ✅ Unchanged | 100 MB limit stays. |
| `EventFile` | ✏️ Rename only → `File` | UUID PK stays. `file`, `original_filename`, `file_size`, `mime_type`, `description`, `tags` columns stay. `is_technical_library` placeholder stays. `db_table` changes from `"event_file"` to `"file"`. |
| `EventFile.is_allowed_extension()` | ✅ Unchanged | Same classmethod. |
| `EventFile.extension` | ✅ Unchanged | Same property. |
| `EventFile.is_image()` / `is_text_preview()` / `get_icon_class()` | ✅ Unchanged | Same helpers. |
| `EventFile._soft_delete()` | ✅ Unchanged | Same pattern. |

---

## Control Layer — Contexts

### `app/events/control_layer/comment_context.py` — `CommentContext`

| Member | Status | Notes |
|---|---|---|
| `CommentContext` class | 🔧 Implementation changes | Class name and file path stay. |
| `__init__(comment_id, actor)` | 🔧 Implementation changes | `self.struct = CommentStruct(comment_id)` stays. |
| `create_from_struct()` | ✅ Unchanged | Pre-loaded build stays. |
| `event` property | 🔧 Implementation changes | Renamed to `thread`. Fetches `ActivityThread` instead of `Event`. `comment.activity_thread_id` replaces `comment.event_id`. |
| `domain` property | ✅ Unchanged | Still reads from thread's domain. |
| `edit()` | ✅ Unchanged | Delegates to `CommentHandler.edit()`. |
| `delete()` | 🔧 Implementation changes | Orphan-file check **removed** (D-003). `CommentAttachment` → `Attachment`. On delete: attachment `comment` FK becomes NULL (demote to thread-level) rather than soft-deleting the attachment. |

### `app/events/control_layer/file_context.py` — `FileContext`

| Member | Status | Notes |
|---|---|---|
| `FileContext` class | 🔧 Implementation changes | Class name and file path stay. |
| `__init__(file_id, actor)` | 🔧 Implementation changes | `EventFile` → `File`. |
| `from_file()` | ✅ Unchanged | Pre-loaded build stays. |
| `delete()` | ✅ Unchanged | Delegates to `FileHandler.soft_delete()`. |

---

## Control Layer — Handlers

### `app/events/control_layer/handlers/event_handler.py` — `EventHandler`

| Member | Status | Notes |
|---|---|---|
| `EventResult` dataclass | ✅ Unchanged | `ok`, `event`, `errors` fields stay. |
| `EventHandler` class | 🔧 Implementation changes | Path and name stay. |
| `CONTENT_FIELDS` / `MACHINE_COMMENT_FIELDS` | ✅ Unchanged | Same field sets. |
| `create()` | 🔧 Implementation changes | Must also write `thread_type=ActivityThreadType.EVENT`, `allow_comments=True`, `allow_direct_attachments=True`. Shadow/machine comment uses `Comment` (renamed). |
| `edit()` | ✅ Unchanged | Diff + shadow/machine comment pattern stays. |
| `_apply_shadow_comment()` | 🔧 Implementation changes | `EventComment` → `Comment`. `event=event` → `activity_thread=event`. |
| `_apply_machine_comment()` | 🔧 Implementation changes | Same. |
| `_validate_create()` / `_validate_edit()` | ✅ Unchanged | Same logic. |
| `_extract_fields()` / `_diff()` / `_apply_field_updates()` | ✅ Unchanged | Same logic. |

### `app/events/control_layer/handlers/comment_handler.py` — `CommentHandler`

| Member | Status | Notes |
|---|---|---|
| `CommentResult` dataclass | 🔧 Implementation changes | `comment: EventComment` → `comment: Comment`. |
| `CommentHandler` class | 🔧 Implementation changes | Path and name stay. |
| `add(event, post_data, files)` | 🔧 Implementation changes | `event` arg becomes `thread: Event` (still an Event row but called thread for clarity). `EventComment.objects.create(event=...)` → `Comment.objects.create(activity_thread=...)`. |
| `edit(old_comment, post_data, files)` | 🔧 Implementation changes | `CommentAttachment` → `Attachment`. `old_comment.event` → `old_comment.activity_thread`. |
| `_carry_forward_attachments()` | 🔧 Implementation changes | `CommentAttachment` → `Attachment`. Same carry-forward logic. |

### `app/events/control_layer/handlers/file_handler.py` — `FileHandler`

| Member | Status | Notes |
|---|---|---|
| `FileResult` dataclass | 🔧 Implementation changes | `file: EventFile` → `file: File`. |
| `FileHandler` class | 🔧 Implementation changes | Path and name stay. |
| `upload(comment, uploaded_file)` | 🔧 Implementation changes | `EventFile` → `File`. `CommentAttachment` → `Attachment`. Must now also populate `thread_id` on `Attachment` (the new mandatory FK). |
| `soft_delete(event_file)` | 🔧 Implementation changes | `EventFile` → `File`. `CommentAttachment` → `Attachment`. Logic is the same. |
| `_validate()` / `_infer_attachment_type()` | 🔧 Implementation changes | `EventFile` → `File`. |

---

## Control Layer — Domain Structs

### `app/events/control_layer/domain_structs/base_event_struct.py`

| Class | Status | Notes |
|---|---|---|
| `BaseEventStruct` | ✏️ Rename only → `EventDetailStruct` | 3-query assembly pattern stays. `EventComment` → `Comment`, `CommentAttachment` → `Attachment`, `EventFile` → `File`. The prefetch on `comments` stays; attachments now also include thread-level (unlinked) attachments. `to_dict()` shape gains `thread_type`, `allow_comments`, `allow_direct_attachments`. |
| `BaseEventStruct.from_components()` | ✅ Unchanged | Pre-loaded build pattern stays. |
| `BaseEventStruct._build_comment_structs()` | 🔧 Implementation changes | Partition logic stays; attachment rows must also be split into comment-linked vs. thread-level (unlinked) sets. |

### `app/events/control_layer/domain_structs/base_event_super_struct.py`

| Class | Status | Notes |
|---|---|---|
| `BaseEventSuperStruct` | ✏️ Rename only → `EventSuperStruct` | Bulk/batch pattern stays. Same 4-query approach. Model name updates (`EventComment` → `Comment`, etc.). |

### `app/events/control_layer/domain_structs/comment_struct.py`

| Class | Status | Notes |
|---|---|---|
| `CommentStruct` | 🔧 Implementation changes | Class name stays. `EventComment` → `Comment`. `CommentAttachment` → `Attachment`. `EventFile` → `File`. `to_dict()` shape is largely unchanged (see below). `__init__` query uses `activity_thread_id` filter instead of `event_id`. |
| `CommentStruct.from_components()` | ✅ Unchanged | Same pre-loaded build. |
| `CommentStruct.to_dict()` | ✅ Unchanged | Same output shape. |

---

## Presentation Layer

### `app/events/presentation_layer/entrypoints/`

| File | Status | Notes |
|---|---|---|
| `events.py` | 🔧 Implementation changes | Entrypoint class names and URL patterns stay. References to `EventContext` stay; `BaseEventStruct` → `EventDetailStruct`. |
| `comments.py` | 🔧 Implementation changes | References to `CommentContext`, `CommentHandler` stay. `EventComment` → `Comment`. |
| `files.py` | 🔧 Implementation changes | References to `FileContext`, `FileHandler` stay. `EventFile` → `File`. |

### `app/events/presentation_layer/search/`

| File | Status | Notes |
|---|---|---|
| `event_search.py` | 🔧 Implementation changes | Query logic stays. Must filter on `thread_type=EVENT` explicitly or rely on `Event.objects` (which already does this via `EventManager`). |

### `app/events/presentation_layer/tools/`

| File | Status | Notes |
|---|---|---|
| `file_previews.py` | 🔧 Implementation changes | `EventFile` → `File`. Extension/type helpers are unchanged. |

---

## Templates

All templates under `app/events/templates/` survive. The template layer accesses struct
dicts — the dict key names in `to_dict()` are unchanged (see `things to keep` for
`CommentStruct.to_dict()` above). Any template that renders `event.event` FK path may
need updating if field names differ, but no template is deleted.

---

## Admin

`app/events/admin.py` survives with model renames applied (`EventComment` → `Comment`,
`CommentAttachment` → `Attachment`, `EventFile` → `File`). Registrations stay.

---

## `app/events/models/__init__.py`

All currently exported names stay, with renames applied:

| Old export | New export |
|---|---|
| `EventComment` | `Comment` |
| `CommentAttachment` | `Attachment` |
| `EventFile` | `File` |
| `Event` | `Event` (unchanged) |
| `EventType` | `EventType` (unchanged) |
| `EventStatus` | `EventStatus` (unchanged) |
| `EventPriority` | `EventPriority` (unchanged) |
| `AttachmentType` | `AttachmentType` (unchanged) |
| — | `ActivityThread` (new export) |
| — | `ActivityThreadType` (new export) |
