---
type: "Technical Decision"
title: "Phase 1 — Model Changes"
description: "No new columns."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-1]
context_tier: 2
---

# Phase 1 — Model Changes

No new columns. No FK target changes. Only class names, manager names, QuerySet names,
and DB table names change.

---

## Class renames

| Old name | New name | File |
|---|---|---|
| `EventComment` | `Comment` | `app/events/models/comment.py` |
| `EventCommentQuerySet` | `CommentQuerySet` | `app/events/models/comment.py` |
| `EventCommentManager` | `CommentManager` | `app/events/models/comment.py` |
| `CommentAttachment` | `Attachment` | `app/events/models/attachment.py` |
| `CommentAttachmentQuerySet` | `AttachmentQuerySet` | `app/events/models/attachment.py` |
| `CommentAttachmentManager` | `AttachmentManager` | `app/events/models/attachment.py` |
| `EventFile` | `File` | `app/events/models/file.py` |

---

## Table renames (requires DB reset)

| Old table name | New table name | Model |
|---|---|---|
| `event_comment` | `comment` | `Comment` |
| `event_comment_attachment` | `attachment` | `Attachment` |
| `event_file` | `file` | `File` |

Set via `Meta.db_table` on each model.

---

## Column layout after Phase 1

### `comment` table (was `event_comment`)

| Column | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | unchanged |
| `event_id` | FK → `event.id` | unchanged — still points at Event, field name stays `event` |
| `parent_comment_id` | FK → `comment.id` (self) | unchanged |
| `content` | TextField | unchanged |
| `is_human_made` | BooleanField | unchanged |
| `deleted_at` | soft-delete | unchanged |
| audit columns | | unchanged |

No column changes.

### `attachment` table (was `event_comment_attachment`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUIDField PK | unchanged |
| `comment_id` | FK → `comment.id` | unchanged — target table renamed but column stays `comment_id` |
| `file_id` | FK → `file.id` | unchanged — target table renamed |
| `display_name` | CharField | unchanged |
| `caption` | TextField | unchanged |
| `display_order` | IntegerField | unchanged |
| `deleted_at` | soft-delete | unchanged |
| audit columns | | unchanged |

No column additions. `comment_id` remains NOT NULL (mandatory) — making it nullable is
Phase 2 work.

### `file` table (was `event_file`)

Columns unchanged. `db_table` changes from `"event_file"` to `"file"`.

---

## `__init__.py` export changes

`app/events/models/__init__.py` — update re-exports:

| Old export | New export |
|---|---|
| `EventComment` | `Comment` |
| `EventCommentQuerySet` | `CommentQuerySet` |
| `CommentAttachment` | `Attachment` |
| `EventFile` | `File` |
| `Event` | `Event` (no change) |
| `EventType` | `EventType` (no change) |
| `EventStatus` | `EventStatus` (no change) |
| `EventPriority` | `EventPriority` (no change) |
| `AttachmentType` | `AttachmentType` (no change) |
