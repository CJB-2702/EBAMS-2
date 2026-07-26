---
type: "Technical Decision"
title: "Phase 2 — Model Changes"
description: "One model changes: Attachment."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-2]
context_tier: 2
---

# Phase 2 — Model Changes

One model changes: `Attachment`. One column is added, one column's nullability changes.
No other models change.

---

## `Attachment` — column changes

### New column: `event`

```python
event = models.ForeignKey(
    "events.Event",
    on_delete=models.CASCADE,
    related_name="attachments",
)
```

- Mandatory (NOT NULL).
- Every attachment belongs to an event. No exceptions.
- `on_delete=CASCADE` — when the event is deleted (soft or hard), its attachments go with it.
- `related_name="attachments"` — accessed as `event.attachments.all()`.

### Changed column: `comment`

```python
comment = models.ForeignKey(
    "events.Comment",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="attachments",
)
```

- Was `NOT NULL` (mandatory). After Phase 2: nullable.
- `on_delete=SET_NULL` — when a comment is deleted, its attachments are demoted to
  standalone event attachments. The attachment row and file are NOT deleted.
- `null=True` when the attachment is standalone (event-level, not inside a comment).

### Full column layout after Phase 2

| Column | Type | Notes |
|---|---|---|
| `id` | UUIDField PK | unchanged |
| `event_id` | FK → `event.id` (NOT NULL) | **NEW** |
| `comment_id` | FK → `comment.id` (nullable) | was NOT NULL, now nullable |
| `file_id` | FK → `file.id` (NOT NULL, PROTECT) | unchanged |
| `display_name` | CharField | unchanged |
| `caption` | TextField | unchanged |
| `display_order` | IntegerField | unchanged |
| `deleted_at` | soft-delete | unchanged |
| audit columns | | unchanged |

### Indexes to add

```python
class Meta:
    db_table = "attachment"
    indexes = [
        models.Index(fields=["event", "created_at"]),
        models.Index(fields=["comment"]),
    ]
```

---

## Service invariant (enforced in control layer, not DB)

When creating an `Attachment` with a non-null `comment`, the control layer must verify:

```python
assert comment.event_id == attachment.event_id
```

A comment cannot be cross-linked to an attachment on a different event. The DB cannot
enforce this cheaply; it is an application-layer invariant.

---

## No changes to `Comment`, `Event`, or `File`

- `Comment.event` FK stays as-is (field name `event`, target `Event`, NOT NULL)
- `Event` model: no new columns
- `File`: no changes

---

## Relationship diagram after Phase 2

```
Event
  ├── Comment        (FK comment.event → Event)
  │     └── Attachment (optional: attachment.comment → Comment)
  └── Attachment     (standalone: attachment.comment = NULL, attachment.event → Event)
```

Both comment-linked and standalone attachments are rows in the same `attachment` table.
The `comment_id` column discriminates: NULL = standalone, non-NULL = comment-linked.
