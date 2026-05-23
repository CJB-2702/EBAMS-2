# Events — Tier 1 Anchor

This file is the **concept anchor** for the events sub-application: occurrences, comments, attachments, and files, with shadow history and soft-delete throughout. Detail lives in the Tier 2 files below.

---

## Core ideas

- **Events are first-class records, not just logs.** An event has a title, type, status, priority, and a real-world start/end. It carries a `domain` FK for row-level scope and is soft-deletable.
- **Comments are immutable.** Editing a comment soft-deletes the old revision and creates a new one with the same `origin_id` chain. Attachments are carried forward to the new revision; old attachment rows remain as history.
- **Files attach to comments, not events directly.** To put a file on an event, the user adds a comment with the file. The events application owns file storage; other apps that need attachments import from it.
- **Shadow history records every change.** Editing an event creates a hidden (soft-deleted) comment recording the full field diff. Status, start, and end changes additionally produce a visible *machine* comment in the timeline.
- **URLs use hashids on integer PKs.** Events and comments are addressed by 8-character hashid-encoded `BigAutoField` PKs at the URL boundary. Files and attachments keep raw UUID7. The control layer always works in integer PKs and model instances — hashids never leak inward.
- **Contexts coordinate cross-table writes; handlers own single-row writes.** `EventContext.delete()` cascades into `CommentContext.delete()`, which checks for and cleans up orphaned files. Simple writes (create event, edit event, add comment) go directly to a handler.

---

## Sub-specifications

| Topic | File |
| :--- | :--- |
| Models, mixins, status/priority choices, permissions, domain scoping | [Events/events.md](Events/events.md) |
| Structs and contexts: `BaseEventStruct`, `EventContext`, `CommentContext` | [Events/event_context_design.md](Events/event_context_design.md) |
| Endpoint-by-endpoint routing: when to call a handler vs a context | [Events/events_endpoints.md](Events/events_endpoints.md) |
| Comment edit, delete, attachment, and file lifecycle invariants | [Events/comment_auditing.md](Events/comment_auditing.md) |
| Slug → hashid migration plan and entrypoint pattern | [Events/pk_hashing_migration.md](Events/pk_hashing_migration.md) |

---

## Reference directionality

This anchor references **only** files inside `Events/`. The events application depends on the Data Domain primitive (see [CoreDomain.md](CoreDomain.md)) and on the layered architecture rules (see [Architecture.md](Architecture.md)) — the relevant constraints are summarised in the bullets above so an events task is answerable from this anchor plus its Tier 2 children.
