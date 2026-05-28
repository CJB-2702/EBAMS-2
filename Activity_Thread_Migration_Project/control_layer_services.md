# Control Layer Services — ActivityThread

This document defines the structs, context, and handler design for the ActivityThread system.
The context hierarchy mirrors the model hierarchy: `Event` is a subclass of `ActivityThread`
(Django MTI), and `EventContext` is a subclass of `ActivityThreadContext`. Callers that work
with events use `EventContext` and get the full thread interface for free via inheritance.
Callers that work with asset threads use `ActivityThreadContext` directly — no Event involved.

---

## Principle: Context Mirrors the Model Hierarchy

`Event` IS-A `ActivityThread` (Django multi-table inheritance). The context layer reflects
this exactly — `EventContext` inherits `ActivityThreadContext` and extends it with event-specific
state, guards, and field operations. There is no delegation or wrapping.

```
Model (Django MTI)                    Context (class inheritance)
──────────────────────────────────    ──────────────────────────────────────────────────
ActivityThread                        ActivityThreadContext
  thread_type                           __init__(thread_id, actor)
  allow_comments                        thread  [lazy property]
  allow_direct_attachments              load()  → ActivityThreadStruct
       ↑ MTI                            add_comment / edit_comment / delete_comment
   Event                                upload_file / attach_file
     domain, title, status ...               ↑ inherits all of the above
     event_start, event_end ...          EventContext
                                           __init__(event_id, actor)
                                           event  [lazy property]
                                           load() → EventDetailStruct  [override]
                                           create_new()  [classmethod factory]
                                           edit() / delete()  [event field writes]
                                           add_comment()  [guard + super()]
                                           upload_file()  [guard + super()]

Asset threads (photo_gallery, documentation)
  → plain ActivityThread rows; no MTI subclass
  → callers use ActivityThreadContext directly; EventContext is never involved
```

Templates and entrypoints that work with events import only `EventContext` and
`EventDetailStruct`. Those that work with asset threads import only `ActivityThreadContext`
and `ActivityThreadStruct`. Neither layer is ever aware of the other's context class.

---

## Structs

### CommentStruct

`CommentStruct` is unchanged from its current definition in
`app/events/control_layer/domain_structs/comment_struct.py`. After the model renames it holds:

- `comment: Comment` (was `EventComment`)
- `attachments: list[Attachment]` (was `list[CommentAttachment]`) — only comment-linked rows
- `files: list[File]` (was `list[EventFile]`) — resolved from the attachment rows
- `revisions: list[Comment]` — prior revisions if `include_revisions=True`

No structural changes. The existing `from_components()` factory and `to_dict()` method carry
forward intact. ActivityThreadContext builds these using `from_components()` so it never
issues per-comment queries.

### ActivityThreadStruct

The fully assembled thread view. This is what ActivityThreadContext returns.
`CommentStruct` objects are assembled internally — callers get ready-to-use structs,
not raw rows.

```python
@dataclass
class ActivityThreadStruct:
    thread: ActivityThread
    thread_type: str                           # ActivityThreadType label (display/filter only)
    allow_comments: bool                       # service-layer gate
    allow_direct_attachments: bool             # service-layer gate
    comment_structs: list[CommentStruct]       # fully assembled; ordered by created_at
    unlinked_attachments: list[Attachment]     # Attachment rows where comment_id is NULL
```

Caller-facing rules:
- `comment_structs` contains only active (`deleted_at=None`), human-made comments unless
  the caller explicitly requests shadow history via a flag on `load()`.
- `unlinked_attachments` are files uploaded directly to the thread without a note —
  available for gallery-style display independently of any comment.
- `allow_comments` and `allow_direct_attachments` are surfaced here so templates can
  conditionally render the comment input and the direct-upload button without any extra
  queries.
- Assembly is 3 queries total (thread + comments + attachments), joined in Python.
  No JOIN or subquery needed.

---

## Class Hierarchy

```
ActivityThreadContext          ← base; owns all thread reads and writes
       ↑ inherits
   EventContext                ← adds event state, event-level guards, event field writes
```

`ActivityThreadContext` owns every thread operation. `EventContext` inherits all of them
and extends with event-specific concerns. There is no delegation between the two — the
relationship is pure inheritance, mirroring the Django MTI model hierarchy.

Asset threads (`photo_gallery`, `documentation`) have no Event row and no Event subclass.
Callers use `ActivityThreadContext` directly with the thread ID from the asset.

---

## ActivityThreadContext

Base context. Handles any thread by its ID. All thread reads and writes live here so
`EventContext` inherits them without duplication.

```python
class ActivityThreadContext:
    """
    Context for a single ActivityThread. Owns all reads and writes for that thread.
    Use directly for asset threads. Subclass for entity-specific behaviour (see EventContext).
    """

    def __init__(self, thread_id: int, actor: AbstractUser | None = None) -> None:
        self._thread_id = thread_id
        self.actor = actor
        self._thread: ActivityThread | None = None

    # ------------------------------------------------------------------ #
    # Lazy state
    # ------------------------------------------------------------------ #

    @property
    def thread(self) -> ActivityThread:
        if self._thread is None:
            self._thread = ActivityThread.objects.get(pk=self._thread_id)
        return self._thread

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def load(self, include_shadow: bool = False) -> ActivityThreadStruct:
        """
        3 queries: thread row, all comments, all attachments.
        Partitions attachments in memory; builds CommentStructs via from_components().
        Returns fully assembled ActivityThreadStruct.

        Query pattern:
          1. ActivityThread.objects.get(pk=self._thread_id)
          2. Comment.objects.filter(activity_thread_id=..., deleted_at__isnull=True)
          3. Attachment.objects.filter(thread_id=..., deleted_at__isnull=True).select_related("file")
        Partition step 3 in Python → build CommentStructs from from_components().
        """

    # ------------------------------------------------------------------ #
    # Comment writes
    # ------------------------------------------------------------------ #

    def add_comment(self, content: str, is_human_made: bool = True) -> Comment:
        """
        Add a human or machine comment. Raises ValueError if allow_comments=False.
        Subclasses may override to add entity-level guards before calling super().
        """

    def add_machine_comment(self, content: str) -> Comment:
        """Visible machine comment (status change, notable transition). deleted_at=None."""

    def add_shadow_comment(self, diff_payload: str) -> Comment:
        """Invisible diff record. deleted_at set at creation time."""

    def edit_comment(
        self, comment: Comment, post_data, files=None
    ) -> CommentResult:
        """
        Edit a comment (immutable revision pattern):
          1. Soft-delete old revision's Attachment rows (demote to thread-level, not delete).
          2. Soft-delete old Comment.
          3. Create new Comment (revision + 1) with same activity_thread.
          4. Re-create Attachment rows pointing to carried-forward files + new comment.
          5. Optionally attach a newly uploaded file.
        """

    def delete_comment(self, comment: Comment) -> None:
        """
        Soft-delete the comment. Clears comment_id on its Attachment rows (demotes to
        thread-level). File rows are NOT deleted — they remain visible as unlinked_attachments.
        No orphan check needed.
        """
        with transaction.atomic():
            now = timezone.now()
            Attachment.objects.filter(
                comment=comment, deleted_at__isnull=True
            ).update(comment=None, updated_at=now, updated_by=self.actor)
            comment._soft_delete(self.actor)

    # ------------------------------------------------------------------ #
    # File + attachment writes
    # ------------------------------------------------------------------ #

    def upload_file(
        self,
        uploaded_file: UploadedFile,
        comment: Comment | None = None,
    ) -> FileResult:
        """
        Validate → create File → create Attachment(thread=self.thread, comment=comment).
        If comment is None (direct-to-thread upload), raises if allow_direct_attachments=False.
        Cross-thread integrity check fires if comment is supplied.
        Returns FileResult(ok, file).
        """
        if comment is None and not self.thread.allow_direct_attachments:
            raise ValueError("This thread does not allow direct file attachments.")

    def attach_file(
        self,
        file: File,
        comment: Comment | None = None,
        attachment_type: str = AttachmentType.DOCUMENT,
        caption: str = "",
        display_order: int = 0,
    ) -> Attachment:
        """
        Create an Attachment row linking an already-uploaded File to this thread.
        Invariant: if comment is given, comment.activity_thread_id must equal self._thread_id.
        """
        if comment is not None and comment.activity_thread_id != self._thread_id:
            raise ValueError(
                "Comment does not belong to this thread. "
                "Cross-thread attachment is not permitted."
            )
        ...
```

Usage for asset threads:

```python
# Photo gallery — no Event involved
ctx = ActivityThreadContext(thread_id=asset.photo_gallery_id, actor=request.user)
ctx.upload_file(request.FILES["photo"])
struct = ctx.load()   # returns ActivityThreadStruct
```

---

## EventContext

Inherits all of `ActivityThreadContext`. Adds event-specific state (the `Event` row),
event-specific guards on inherited methods, and the event field edit/delete operations.
Because `Event.pk == ActivityThread.pk`, the same integer initialises both layers.

```python
@dataclass
class EventDetailStruct:
    event: Event
    comment_structs: list[CommentStruct]       # fully assembled; each has .attachments, .files
    unlinked_attachments: list[Attachment]     # thread-level files with no comment
    can_comment: bool
    detail: dict | None                        # event type-specific detail record


class EventContext(ActivityThreadContext):
    """
    Full context for an Event. Inherits all thread operations from ActivityThreadContext.
    event_id == thread_id because Event IS-A ActivityThread via Django MTI — the same
    integer PK identifies both the event row and its activity_thread parent row.
    Use this for all event-related interactions — templates and entrypoints never import
    ActivityThreadContext or ActivityThreadStruct.
    """

    def __init__(self, event_id: int, actor: AbstractUser | None = None) -> None:
        super().__init__(thread_id=event_id, actor=actor)
        self._event: Event | None = None

    # ------------------------------------------------------------------ #
    # Factory — event creation
    # ------------------------------------------------------------------ #

    @classmethod
    def create_new(cls, post_data, actor: AbstractUser) -> "EventContext":
        """
        Create an Event (and its ActivityThread parent row) in a single Django MTI insert.
        Django handles both rows atomically — no explicit thread creation step.
        Returns a ready-to-use EventContext with the event pre-warmed in cache.
        """
        errors = cls._validate_create(post_data)
        if errors:
            raise ValueError(errors)

        event = Event.objects.create(
            # ActivityThread (parent) fields
            thread_type=ActivityThreadType.EVENT,
            allow_comments=True,
            allow_direct_attachments=True,
            # Event fields
            domain_id=post_data["domain_id"],
            title=post_data["title"].strip(),
            ...
            created_by=actor,
            updated_by=actor,
        )
        # event.pk == activity_thread row PK, guaranteed by Django MTI

        ctx = cls(event_id=event.pk, actor=actor)
        ctx._event = event      # pre-warm; no re-fetch needed
        return ctx

    # ------------------------------------------------------------------ #
    # Lazy state
    # ------------------------------------------------------------------ #

    @property
    def event(self) -> Event:
        if self._event is None:
            self._event = Event.objects.get(pk=self._thread_id)
        return self._event

    # ------------------------------------------------------------------ #
    # Reads — override to return EventDetailStruct
    # ------------------------------------------------------------------ #

    def load(self, include_shadow: bool = False) -> EventDetailStruct:
        """
        Calls super().load() for thread data, merges with event row and detail record.
        Callers receive a single struct — no knowledge of ActivityThread required.
        """
        thread_struct = super().load(include_shadow=include_shadow)
        return EventDetailStruct(
            event=self.event,
            comment_structs=thread_struct.comment_structs,
            unlinked_attachments=thread_struct.unlinked_attachments,
            can_comment=thread_struct.allow_comments,
            detail=self._load_detail(),
        )

    # ------------------------------------------------------------------ #
    # Event writes
    # ------------------------------------------------------------------ #

    def edit(self, post_data) -> EventResult:
        """
        Edit event fields. Diffs old vs new values, emits shadow comment always,
        machine comment on notable field changes (status, times).
        Delegates comment writes to inherited add_shadow_comment / add_machine_comment.
        """
        errors = self._validate_edit(post_data)
        if errors:
            return EventResult(ok=False, event=self.event, errors=errors)

        changes = self._diff(post_data)
        if not changes:
            return EventResult(ok=True, event=self.event)

        with transaction.atomic():
            self.add_shadow_comment(self._build_diff_payload(changes))
            if self._has_notable_changes(changes):
                self.add_machine_comment(self._build_machine_message(changes))
            self._apply_field_updates(post_data)

        return EventResult(ok=True, event=self.event)

    def delete(self) -> None:
        """Soft-delete the event."""
        self.event._soft_delete(self.actor)

    # ------------------------------------------------------------------ #
    # Guards — override inherited thread writes with event-level checks
    # ------------------------------------------------------------------ #

    def add_comment(self, content: str, is_human_made: bool = True) -> Comment:
        """Cannot comment on a soft-deleted event."""
        if self.event.deleted_at is not None:
            raise ValueError("Cannot add a comment to a deleted event.")
        return super().add_comment(content, is_human_made)

    def upload_file(self, uploaded_file, comment: Comment | None = None) -> FileResult:
        """Cannot upload to a soft-deleted event."""
        if self.event.deleted_at is not None:
            raise ValueError("Cannot upload files to a deleted event.")
        return super().upload_file(uploaded_file, comment)

    # ------------------------------------------------------------------ #
    # Private
    # ------------------------------------------------------------------ #

    def _load_detail(self) -> dict | None: ...
    def _validate_create(post_data) -> list[str]: ...
    def _validate_edit(self, post_data) -> list[str]: ...
    def _diff(self, post_data) -> list[dict]: ...
    def _apply_field_updates(self, post_data) -> None: ...
    def _has_notable_changes(self, changes: list[dict]) -> bool: ...
    def _build_diff_payload(self, changes: list[dict]) -> str: ...
    def _build_machine_message(self, changes: list[dict]) -> str: ...
```

### Typical entrypoint usage

```python
# Read
ctx = EventContext(event_id=42, actor=request.user)
struct = ctx.load()               # EventDetailStruct — no ActivityThread visible

# Create
ctx = EventContext.create_new(post_data, actor=request.user)

# Edit event fields
ctx = EventContext(event_id=42, actor=request.user)
result = ctx.edit(post_data)

# Add a comment (with optional file)
ctx.add_comment("Maintenance completed.")
ctx.upload_file(request.FILES["photo"], comment=last_comment)

# Edit a comment
ctx.edit_comment(comment, post_data, files=request.FILES)

# Delete a comment
ctx.delete_comment(comment)
```

---

## Asset Thread Usage (ActivityThreadContext directly)

Asset threads have no Event — there is no EventContext for them.
Callers use `ActivityThreadContext` directly with the thread FK from the Asset.

```python
# Read photo gallery
ctx = ActivityThreadContext(thread_id=asset.photo_gallery_id, actor=request.user)
struct = ctx.load()   # ActivityThreadStruct; comment_structs will be empty if allow_comments=False

# Upload to documentation thread
ctx = ActivityThreadContext(thread_id=asset.documentation_id, actor=request.user)
ctx.upload_file(request.FILES["manual"])
ctx.add_comment("Rev B manual uploaded.")
```

Asset creation still uses a handler (no context equivalent since the asset ID doesn't
exist yet):

```python
class AssetHandler:
    def create(self, post_data, actor) -> AssetResult:
        with transaction.atomic():
            photo_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.PHOTO_GALLERY,
                allow_comments=False,
                created_by=actor, updated_by=actor,
            )
            doc_thread = ActivityThread.objects.create(
                thread_type=ActivityThreadType.DOCUMENTATION,
                allow_comments=True,
                created_by=actor, updated_by=actor,
            )
            asset = Asset.objects.create(
                photo_gallery=photo_thread,
                documentation=doc_thread,
                ...
            )
        return AssetResult(ok=True, asset=asset)
```

---

## Service Invariants Summary

| Rule | Enforced by |
|---|---|
| Comments cannot be added to a thread with `allow_comments=False` | `ActivityThreadContext.add_comment` |
| Direct file uploads blocked when `allow_direct_attachments=False` | `ActivityThreadContext.upload_file` |
| An attachment's comment must belong to the same thread | `ActivityThreadContext.attach_file` |
| Comment deletion demotes attachments to thread-level, never deletes files | `ActivityThreadContext.delete_comment` |
| Cannot comment or upload on a soft-deleted event | `EventContext.add_comment`, `EventContext.upload_file` |
| Thread creation is atomic with entity creation | Django MTI (`EventContext.create_new`); `AssetHandler.create` |
| A thread is never shared between two entities | MTI parent-link / OneToOneField constraints on owner models |
| Templates and entrypoints only ever import `EventContext` and `EventDetailStruct` | Layer boundary |
