---
type: "Technical Decision"
title: "Phase 3 — Goal: Event / ActivityThread Proxy Split"
description: "After Phase 2, comments and attachments belong to Event directly."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project, phase-3]
context_tier: 2
---

# Phase 3 — Goal: Event / ActivityThread Proxy Split

## Problem

After Phase 2, comments and attachments belong to `Event` directly. This works for events
but makes it impossible for other domain entities (e.g. `Asset`) to have an activity
thread — because they are not events and should not create Event rows to get thread
functionality.

## What this phase does

Introduce `ActivityThread` as a **restricted proxy alias** of `Event`. A single physical
table (`event`) holds all thread types. `ActivityThread` restricts the default manager to
non-event rows and auto-fills sentinel values for required event fields.

This allows:
- `Asset` to own two named thread rows (`photo_gallery`, `documentation`) via
  `OneToOneField("events.ActivityThread")`
- Existing event rows to remain unchanged — they are still `Event` rows in the same table
- Comments and attachments to be retargeted at `ActivityThread` (the proxy) rather than
  `Event` directly

## Prerequisite

Phase 2 complete. `Attachment` has a direct `event` FK. In this phase that column is
renamed from `event` to `thread` and retargeted from `Event` to the `ActivityThread`
proxy. The pattern (mandatory single-row FK, optional comment FK) is unchanged.

## Direction of the proxy relationship

```
Event              ← concrete model, physical table owner, source of all functionality
  │
  └── ActivityThread  ← restricted proxy alias (non-event rows only, sentinel injection)
```

`ActivityThread` IS an `Event` — same row, same table, same PK. The proxy adds no new
capabilities. It restricts the query surface and injects sentinels for non-event rows.

**ActivityThread is not the parent. Event is not a subclass of ActivityThread.**

## What this phase does NOT do

- No new physical DB tables
- No structural changes to `Comment` or `Attachment` beyond FK renames
- No presentation layer changes (presentation layer is repaired in Phase 4)

## Success criteria

- `Event.objects.all()` returns only event rows
- `ActivityThread.objects.all()` returns only non-event rows
- `Event.threads.all()` returns all rows (internal use only)
- Asset creation produces two `ActivityThread` rows atomically
- Comments and attachments resolve to any thread type by `id`
- DB reset + seed completes cleanly
