---
tier: 1
type: "Domain Doc"
title: "Events"
description: "Concept anchor for the events sub-application: occurrences, comments, attachments, and files, with shadow history and soft-delete throughout."
tags: [applications, domain-doc, events]
context_tier: 2
---

# Events

The events sub-application: occurrences, comments, attachments, and files, with shadow history and soft-delete throughout. Detail lives in the Tier 2 files below.

## Status

Active — nearly every sub-application emits or consumes events.

## Core ideas

- **Events are first-class records, not just logs.** An event has a title, type, status, priority, and a real-world start/end. It carries a `domain` FK for row-level scope and is soft-deletable.
- **Comments are immutable.** Editing a comment soft-deletes the old revision and creates a new one with the same `origin_id` chain. Attachments are carried forward to the new revision; old attachment rows remain as history.
- **Files attach to comments, not events directly.** To put a file on an event, the user adds a comment with the file. The events application owns file storage; other apps that need attachments import from it.
- **Shadow history records every change.** Editing an event creates a hidden (soft-deleted) comment recording the full field diff. Status, start, and end changes additionally produce a visible *machine* comment in the timeline.
- **URLs use hashids on integer PKs.** Events and comments are addressed by 8-character hashid-encoded `BigAutoField` PKs at the URL boundary. Files and attachments keep raw UUID7. The control layer always works in integer PKs and model instances — hashids never leak inward.
- **Contexts coordinate cross-table writes; handlers own single-row writes.** `EventContext.delete()` cascades into `CommentContext.delete()`, which checks for and cleans up orphaned files. Simple writes (create event, edit event, add comment) go directly to a handler.

## Deep specs

See [events/index.md](events/index.md) for the full, machine-routable index of Tier 2 guides and skeletons (models, event context design, endpoint routing, comment auditing, PK hashing migration).

## Skeleton instructions

For task setup (integrating another sub-app with events): [skeleton_instructions.md](events/skeleton_instructions.md).

## Reference directionality

This anchor references **only** files inside `events/`. The events application depends on the Data Domain primitive (see [core_domain.md](core_domain.md)) and on the layered architecture rules (see [../Architecture.md](../Architecture.md)) — the relevant constraints are summarised in the bullets above so an events task is answerable from this anchor plus its Tier 2 children.
