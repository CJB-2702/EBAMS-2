# Phase 2 — Goal: Attachment Denormalization

## Problem

Currently, every file attached to an event must be carried by a `Comment` row. There is
no way to attach a file directly to an event — a "machine comment" is created as a
carrier, which pollutes the comment timeline and complicates the upload path.

`Attachment` currently has:
- `comment` FK — mandatory (NOT NULL)
- No direct event reference

This means: attachment → comment → event. Two hops to get to the event. No standalone
file attachment is possible.

## What this phase does

Add a mandatory `event` FK directly to `Attachment`. Make the `comment` FK nullable.

```
Attachment (after Phase 2)
  ├── event    FK → Event  (mandatory — every attachment belongs to an event)
  └── comment  FK → Comment (nullable — only set when file is inline to a comment)
```

Attachments without a comment are "standalone event attachments." They appear in the
event's file list rather than nested under a comment.

## Scope boundary — CRITICAL

**Everything in this phase points at `Event` directly. `ActivityThread` does not exist
in this phase. Do not introduce the ActivityThread concept, proxy model, or any related
patterns during Phase 2 work.**

The FK rename from `event` → `thread` and the retarget to `ActivityThread` is Phase 3
work. Phase 2 establishes the standalone-attachment pattern; Phase 3 generalizes it to
any thread type.

## What this phase does NOT do

- No `thread_type` discriminator column
- No `allow_comments` / `allow_direct_attachments` flags
- No `ActivityThread` proxy model
- No changes to the `Event` model
- No changes to `Comment` FK targets
- No Asset model changes

## Success criteria

- A file can be attached to an event with `comment=None`
- Deleting a comment sets `attachment.comment` to NULL rather than deleting the attachment
- No machine-comment workaround is needed for event-level file attachments
- DB reset + seed completes cleanly

## Prerequisite

Phase 1 complete. Class names (`Comment`, `Attachment`, `File`) are in place before
this schema change is applied.
