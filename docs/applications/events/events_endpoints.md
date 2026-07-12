# Events Endpoints — Handler vs Context routing

This document covers every endpoint in the events app and answers one question for each: should the entrypoint call the handler directly, or route through a context class? For struct and context class descriptions see [event_context_design.md](event_context_design.md). For the slug-to-hashid migration see [pk_hashing_migration.md](pk_hashing_migration.md).

---

## General rule

**Go direct to the handler** when the operation affects only the object being acted on — no parent-child cleanup, no cross-table cascades.

**Use a context** when the operation has effects outside the object itself — particularly deletes where child rows and potentially orphaned files must also be cleaned up, or when the full event graph needs to be loaded in one pass.

Within this application, most write actions are simple CRUD on one row. The context is the exception, not the default.

---

## ID resolution pattern

All event and comment URLs expose a hashid-encoded integer PK. The entrypoint decodes the hashid to an integer PK and fetches the model instance before calling any handler or context.

```python
from app.utils.hashids import decode_hash

event_id = decode_hash(hash_str)         # returns int or None
event = get_object_or_404(Event.objects.active(), pk=event_id)
# Permission check uses fields on the resolved instance
# Handler or context is called after the permission check passes
```

The control layer (handlers, contexts, structs) works with integer PKs and model instances — never with hashids. Decoding is a presentation-layer concern and stays in the entrypoint.

For file endpoints, the UUID7 is used directly in the URL — no hashid involved.

---

## Endpoints

### `GET /events/` — event list
**Routing:** direct to search function (`list_events_for_user()`). No handler, no context. Read-only list.

### `GET /events/create/` — event create form
**Routing:** no handler call on GET. Renders the form.

### `POST /events/create/` — event create submit
**Routing:** direct to `EventHandler.create()`. Creating an event has no children yet. `EventContext` has no `create()` method.

### `GET /events/<hash>/` — event detail
**Routing:** build a `BaseEventStruct` (or `EventContext`) after resolving the hashid.

```
event_detail() entrypoint
  ├── event_id = decode_hash(hash)
  ├── event = get_object_or_404(Event.objects.active(), pk=event_id)
  ├── permission check (domain membership, created_by)
  └── ctx = EventContext(event_id, actor)   ← 4 fixed queries
```

### `GET /events/<hash>/edit/` — event edit form
**Routing:** no handler on GET. Decode hashid, fetch event, permission check, render form.

### `POST /events/<hash>/edit/` — event edit submit
**Routing:** direct to `EventHandler.edit()`. The handler internally calls `_apply_shadow_comment()` and, when status or time fields change, `_apply_machine_comment()`. No cross-table effects requiring a context.

### `POST /events/<hash>/delete/` — event soft-delete
**Routing:** through `EventContext.delete()`. This is the primary use case for a context. Deleting an event must also soft-delete child comments and soft-delete any orphaned files. The event model's `_soft_delete()` only marks the event row — the context owns the cascade.

```
event_soft_delete() entrypoint
  ├── event_id = decode_hash(hash)
  ├── event = get_object_or_404(Event.objects.active(), pk=event_id)
  ├── permission check (must happen before context — context is not a permission layer)
  └── ctx = EventContext(event_id, actor)
        └── ctx.delete()
              ├── event._soft_delete(actor)
              └── for each comment_struct in ctx.struct.comments:
                    CommentContext.create_from_struct(comment_struct, actor).delete()
                      ├── comment._soft_delete(actor)
                      └── orphaned files soft-deleted
```

### `GET /events/<hash>/comments/add/` — add comment form
**Routing:** no handler on GET.

### `POST /events/<hash>/comments/add/` — add comment submit
**Routing:** direct to `CommentHandler.add()`. One row created; no parent-child effects.

### `GET /events/<hash>/comments/<hash>/edit/` — edit comment form
**Routing:** no handler on GET.

### `POST /events/<hash>/comments/<hash>/edit/` — edit comment submit
**Routing:** direct to `CommentHandler.edit()`. Editing creates a new revision, soft-deletes the old one, and carries forward attachment links — all inside the handler.

### `POST /events/<hash>/comments/<hash>/delete/` — comment soft-delete
**Routing:** through `CommentContext.delete()`. Deleting a comment must check whether any files attached to that comment are now orphaned. The comment model's `_soft_delete()` only marks the comment row.

```
comment_soft_delete() entrypoint
  ├── event_id = decode_hash(event_hash)
  ├── comment_id = decode_hash(comment_hash)
  ├── permission check
  └── CommentContext(comment_id, actor).delete()
        ├── comment._soft_delete(actor)
        └── for each attachment:
              if no other active CommentAttachment rows reference this file:
                FileHandler(actor).soft_delete(file)
```

### `POST /events/<hash>/files/upload/` — file upload
**Routing:** direct to `FileHandler.upload()`. Creates an `EventFile` row and one `CommentAttachment` link. Self-contained.

### `GET /events/files/<uuid>/download/` — file download
**Routing:** no handler. Resolve file by UUID7, serve directly.

### `GET /events/files/<uuid>/inline/` — file inline
**Routing:** no handler. Read-only.

### `POST /events/files/<uuid>/delete/` — file soft-delete
**Routing:** direct to `FileHandler.soft_delete()`. The user has explicitly chosen to delete this file. `FileHandler.soft_delete()` bulk-soft-deletes all `CommentAttachment` rows referencing the file, then soft-deletes the `EventFile` row.

```
file_soft_delete() entrypoint
  ├── event_file = get_object_or_404(EventFile.objects.active(), pk=file_id)
  ├── permission check
  └── FileHandler(actor).soft_delete(event_file)
```

This is distinct from the orphan-check path inside `CommentContext.delete()` — that path only soft-deletes a file when it determines no active references remain. This path soft-deletes unconditionally because the intent is explicit. The two paths must not be conflated.
