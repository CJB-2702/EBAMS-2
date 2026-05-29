# Phase 3 — Control Layer Changes

---

## Manager restructure on `Event`

The current `EventManager` returns all non-deleted rows. After Phase 3 it must filter to
`thread_type=EVENT` rows only. Any caller that previously expected `Event.objects` to
return non-event rows will get fewer results.

```python
# Before Phase 3 — EventManager returns all rows
Event.objects.all()  # all non-deleted rows

# After Phase 3 — EventManager returns event rows only
Event.objects.all()  # only thread_type="event" rows
Event.threads.all()  # all rows — internal context layer use only
```

`EventQuerySet.visible_to()` must also filter to `thread_type=EVENT` so it never returns
asset-thread rows.

---

## `EventContext` — fetch path change

`EventContext.row` must fetch via `Event.threads` (unfiltered) so that
`ActivityThreadContext` can inherit without overriding the fetch path.

```python
@property
def row(self) -> Event:
    if self._row is None:
        # AnyThreadManager — resolves any row by id regardless of thread_type.
        self._row = Event.threads.get(pk=self._id)
    return self._row
```

`create_new()` writes with `thread_type=ActivityThreadType.EVENT`:

```python
@classmethod
def create_new(cls, post_data: dict, actor) -> "EventContext":
    event = Event.objects.create(
        thread_type=ActivityThreadType.EVENT,
        allow_comments=True,
        allow_direct_attachments=True,
        ...
    )
```

---

## New: `ActivityThreadContext` (thin alias)

```python
class ActivityThreadContext(EventContext):
    """Restricted alias of EventContext for non-event rows. Adds nothing."""
    pass
```

File: `app/events/control_layer/activity_thread_context.py`

Inherits all thread operations (comments, attachments, file uploads) from `EventContext`
with zero overrides. Reserved for future asset-thread-specific divergence — if none
materializes, it stays as-is.

---

## New: `ActivityThreadStruct` alias

```python
ActivityThreadStruct = EventDetailStruct
```

No separate struct class. ActivityThread rows and Event rows produce the same struct.

---

## Struct field updates

`EventDetailStruct` gains three new fields:

```python
@dataclass(frozen=True)
class EventDetailStruct:
    ...
    thread_type: str
    allow_comments: bool
    allow_direct_attachments: bool
    ...
```

`from_components()` and `to_dict()` updated to include these fields.

---

## `CommentStruct` — field rename

`event_id` field in `CommentStruct` becomes `activity_thread_id` to match the renamed
model column.

---

## `AttachmentStruct` — field rename

`event_id` (from Phase 2) becomes `thread_id` to match the renamed model column.

---

## `AssetHandler` — thread creation

Asset creation must create two `ActivityThread` rows atomically:

```python
class AssetHandler:
    def create(self, post_data, actor) -> AssetResult:
        with transaction.atomic():
            photo_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.PHOTO_GALLERY,
                allow_comments=False,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=actor,
                updated_by=actor,
                # title, event_type → filled with "__thread__" by ActivityThread.save()
            )
            doc_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.DOCUMENTATION,
                allow_comments=True,
                allow_direct_attachments=True,
                domain_id=post_data["domain_id"],
                created_by=actor,
                updated_by=actor,
            )
            asset = Asset.objects.create(
                photo_gallery=photo_thread,
                documentation=doc_thread,
                ...
            )
        return AssetResult(ok=True, asset=asset)
```

Both threads are created before the Asset row — no lazy thread creation.

---

## `ThreadPolicy` (new)

Pure-read policy class. Reads thread flags and answers capability questions. No DB writes.

```python
class ThreadPolicy:
    def __init__(self, row: Event) -> None: ...

    def can_add_comment(self) -> bool: ...         # row.allow_comments
    def can_attach_directly(self) -> bool: ...     # row.allow_direct_attachments
    def can_attach_to_comment(self) -> bool: ...   # always True if can_add_comment
    def is_event_row(self) -> bool: ...            # row.thread_type == ActivityThreadType.EVENT
```

File: `app/events/control_layer/policies/thread_policy.py`

---

## Handler updates

### `EventHandler.create()`

Must now also write:
- `thread_type=ActivityThreadType.EVENT`
- `allow_comments=True`
- `allow_direct_attachments=True`

### `FileHandler.upload()`

Column rename: `event` argument becomes `thread` (matches new FK name on `Attachment`).

### `CommentHandler.add()`

`activity_thread` argument replaces `event`. `Comment.objects.create(activity_thread=...)`.

---

## Manager access rules (summary)

| Manager | Via | Allowed in |
|---|---|---|
| `EventManager` | `Event.objects` | templates, entrypoints, `EventContext.create_new` |
| `AssetThreadManager` | `ActivityThread.objects` | `AssetHandler`, asset entrypoints |
| `AnyThreadManager` | `Event.threads` | `EventContext.row` property only |

`Event.threads` must never appear in templates or entrypoints.
