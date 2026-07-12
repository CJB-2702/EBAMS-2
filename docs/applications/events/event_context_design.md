---
type: "Domain Doc"
title: "Event Context Design"
description: "This document covers the structs, context classes, and their interactions with existing handlers."
tags: [events, domain-doc]
context_tier: 2
---

# Event Context Design

This document covers the structs, context classes, and their interactions with existing handlers. Endpoint routing decisions live in [events_endpoints.md](events_endpoints.md). The migration from slugs to hashid-encoded integer PKs is documented in [pk_hashing_migration.md](pk_hashing_migration.md). For the file/attachment lifecycle invariants the contexts enforce, see [comment_auditing.md](comment_auditing.md).

---

## 1. Philosophy

Handlers (`EventHandler`, `CommentHandler`, `FileHandler`) each own write operations on a single model. They do not know about each other and do not manage parent-child relationships.

Context classes fill that gap: when an action has effects that cross object boundaries (a delete cascading from event to comments to attachments to orphaned files), a context owns the coordination. It delegates row-level work to the appropriate handler or model method but is responsible for the sequence and cross-table decisions.

Structs pre-load a complete object graph in a fixed number of queries, giving contexts and external callers all the data they need without N+1 queries.

**External callers are the primary audience.** When another application needs to work with an event, these classes are the stable, single entry point. Within events itself, most single-object CRUD actions go directly to the handlers.

**Contexts do not have `create()` methods.** Creation is handled by a handler or factory, which produces the row. A context can be built from the result if further operations are needed.

---

## 2. `_soft_delete` convention

Model classes expose `_soft_delete(actor)` as a protected method (underscore prefix). Only control-layer code — handlers and contexts — should call it. Presentation-layer code, other models, and utilities must not call `_soft_delete` directly.

Each model's `_soft_delete()` marks only that one row as deleted. It does not cascade to children. Parent-child cascades are the context layer's job.

---

## 3. Existing infrastructure

### Models (`app/events/models/`)

| Class | PK type | Role |
| :--- | :--- | :--- |
| `Event` | Integer (BigAutoField) | Base event row; URL-addressed via hashid-encoded PK. |
| `EventComment` | Integer (BigAutoField) | Immutable once saved; edits produce new revisions. |
| `CommentAttachment` | UUID7 | Join record linking a comment to a file. |
| `EventFile` | UUID7 | Uploaded file record; URL-addressed by raw UUID. |

### Handlers (`app/events/control_layer/handlers/`)

| Class | Methods | Role |
| :--- | :--- | :--- |
| `EventHandler` | `create()`, `edit()` | Writes on Event rows. Shadow + machine comments on edit. |
| `CommentHandler` | `add()`, `edit()` | Writes on EventComment rows. Carries attachments forward on edit. |
| `FileHandler` | `upload()`, `soft_delete()` | Creates EventFile + CommentAttachment on upload; bulk-soft-deletes attachments and soft-deletes the file on delete. |

Planned addition to `EventHandler`: `_apply_machine_comment(event, message)` — creates a **visible** machine-generated comment in the event timeline, called from `edit()` when the diff contains a status change or a change to `event_start`/`event_end`. Distinct from the existing `_apply_shadow_comment()` which writes a soft-deleted audit record.

---

## 4. `to_dict` convention

Every struct class defines a `to_dict()` method returning a plain `dict`. Templates, external callers, and debug tooling consume the struct without depending on model internals. Each struct defines its own `to_dict()` — no shared mixin. Nested structs call their own `to_dict()` recursively.

```
CommentStruct.to_dict() → {
  "comment_id": int,
  "content": str,
  "revision": int,
  "is_human_made": bool,
  "created_by": str,
  "created_at": str  (ISO 8601),
  "attachments": [{"attachment_id": str (uuid), "file_id": str (uuid), ...}, ...],
}

BaseEventStruct.to_dict() → {
  "event_id": int,
  "title": str,
  "status": str,
  ...
  "comments": [CommentStruct.to_dict(), ...],
}
```

---

## 5. `CommentStruct`

**Location:** `app/events/control_layer/domain_structs/comment_struct.py`

Data container for a single `EventComment` and its related rows: `CommentAttachment` (0..N) → `EventFile` (1 per attachment). Optionally also fetches soft-deleted previous revisions via the `origin_id` chain.

**Constructor:** `CommentStruct(comment_id, include_revisions=False)`. Issues up to three queries (comment, attachments, optional revisions).

**Class method:** `CommentStruct.from_components(comment_row, attachments, files, revisions=None)` accepts rows already fetched by a parent caller. Issues no DB queries.

| Field | Type |
| :--- | :--- |
| `comment` | `EventComment` |
| `attachments` | `list[CommentAttachment]` |
| `files` | `list[EventFile]` |
| `revisions` | `list[EventComment]` (empty unless include_revisions=True) |

---

## 6. `BaseEventStruct`

**Location:** `app/events/control_layer/domain_structs/base_event_struct.py`

Data container for a single Event and its entire child graph: `Event` → `EventComment` (0..N) → `CommentAttachment` (0..N) → `EventFile` (1 per attachment). Loads everything in a fixed number of queries (4) and distributes rows to child `CommentStruct` instances via `from_components`.

**Constructor:** `BaseEventStruct(event_id, include_shadow_comments=False)`. Issues four queries.

**Class method:** `BaseEventStruct.from_components(event_row, comment_rows, attachment_rows, file_rows)` — zero queries.

Fields: `event` (Event), `comments` (list[CommentStruct]). `to_dict()` returns a dict including nested `CommentStruct.to_dict()` per child.

---

## 7. `BaseEventSuperStruct`

**Location:** `app/events/control_layer/domain_structs/base_event_super_struct.py`

**Status:** Placeholder. No confirmed use case. Built so the pattern exists when needed.

Data container for a list of Events and their complete child graphs. Fetches all events, comments, attachments, and files in four queries across the entire batch, then distributes rows to `BaseEventStruct.from_components`. Avoids the 4×N cost of constructing `BaseEventStruct` per event in a loop.

---

## 8. `CommentContext`

**Location:** `app/events/control_layer/comment_context.py`

Stateful control object for a single comment. Owns a `CommentStruct`. Exists primarily to own the `delete()` cascade — comment deletion must also check for and clean up orphaned files.

**No `create()` method.** Adding a comment is handled by `CommentHandler.add()` or via `EventContext.add_comment()`.

**Constructors:**
- `CommentContext(comment_id, actor)` — builds a `CommentStruct` internally.
- `CommentContext.create_from_struct(comment_struct, actor)` — zero extra queries; used by `EventContext` when it already holds child comment structs.

**Lazy-loaded properties:** `event` (the parent Event row, with `select_related("domain")`), `domain` (via `self.event`).

**Methods:**

| Method | Delegates to | Notes |
| :--- | :--- | :--- |
| `edit(post_data)` | `CommentHandler.edit(self.struct.comment, post_data)` | Thin wrapper. |
| `delete()` | See below | Owns the attachment/file cascade. |

**`delete()` cascade detail:** soft-delete the comment row, then for each attachment in the struct, check if any other comment still references that file via an active `CommentAttachment` row; if not, call `FileHandler.soft_delete(file)` (which bulk-soft-deletes the attachment links and soft-deletes the file row).

The `other_refs` check matters because `CommentHandler.edit()` carries attachment rows forward to new revisions. A file may be referenced by multiple revisions; it is only soft-deleted when no other active attachment row still points to it.

---

## 9. `EventContext`

**Location:** `app/events/control_layer/event_context.py`

Stateful control object for a single event. Owns a `BaseEventStruct`. Primary entry point for external callers who need to work with an event. Coordinates cross-table writes; delegates single-row writes to handlers.

**No `create()` method.** Event creation is handled by `EventHandler.create()`, which returns the new row.

**Constructors:**
- `EventContext(event_id, actor)` — builds a `BaseEventStruct` internally.
- `EventContext.create_from_struct(base_event_struct, actor)` — zero extra queries.

**Methods:**

| Method | Delegates to | Notes |
| :--- | :--- | :--- |
| `edit(post_data)` | `EventHandler.edit(self.struct.event, post_data)` | Thin wrapper. |
| `add_comment(post_data)` | `CommentHandler.add(self.struct.event, post_data)` | Provides the event; caller doesn't need to pass it. |
| `add_attachment(uploaded_file)` | See below | Creates a visible machine comment + attaches file. |
| `delete()` | See below | Owns the full cascade. |

**`add_attachment()` detail:** create an `EventComment` with `is_human_made=False`, `deleted_at=None` (visible), `content=f"File added: {uploaded_file.name}"`. Then `FileHandler.upload(machine_comment, uploaded_file)` creates the `EventFile` and the `CommentAttachment`.

**`delete()` cascade detail:** soft-delete the event row, then for each `comment_struct` in `self.struct.comments`, call `CommentContext.create_from_struct(comment_struct, actor).delete()`. `EventContext` does not import or touch comment, attachment, or file models directly — all child cleanup is delegated to `CommentContext`.

`create_from_struct` is zero-cost here because `BaseEventStruct` already holds all comment data.

---

## 10. ID boundary — hashids at the URL layer

All URLs referencing an event or comment expose a hashid-encoded integer PK. Internally, the control layer always works with integer PKs and model instances — never with hashids or slugs.

```
URL /events/Yz3kP9m2/
  → entrypoint decodes "Yz3kP9m2" → event_id (int)
  → get_object_or_404(Event.objects.active(), pk=event_id)
  → EventContext(event_id, actor)
```

The encoding utility lives in `app/utils/hashids.py`. Only entrypoints call it. Nothing inside the control layer or struct layer is aware of hashids.

See [pk_hashing_migration.md](pk_hashing_migration.md) for the full migration plan.

---

## 11. File locations

```
app/events/control_layer/
  domain_structs/
    comment_struct.py            ← CommentStruct
    base_event_struct.py         ← BaseEventStruct
    base_event_super_struct.py   ← BaseEventSuperStruct (placeholder)
  event_context.py               ← EventContext
  comment_context.py             ← CommentContext
  handlers/
    event_handler.py             ← add _apply_machine_comment()
    comment_handler.py
    file_handler.py

app/utils/
  hashids.py                     ← encode_id() / decode_hash() utility
```
