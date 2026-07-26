---
okf_version: "0.1"
type: "Index"
title: "Events Knowledge Bundle"
description: "Events sub-application: comments, files, shadow history, contexts, and endpoint routing."
tags: [applications, events, index, okf]
context_tier: 2
personas: [backend, business]
---

# Events

The event tracking sub-application: comments, attachments, shadow history, and event contexts.

## Guides

- [Events Domain](events.md) — authoritative source of truth for the events sub-application.
- [Event Context Design](event_context_design.md) — structs, context classes, and handler interactions.
- [Events Endpoints — Handler vs Context Routing](events_endpoints.md) — per-endpoint routing decisions.
- [Comment Auditing — History, Attachments, and File Lifecycle](comment_auditing.md) — comment editing, deletion, and cleanup.
- [PK Hashing Migration — Slugs to Hashids](pk_hashing_migration.md) — migration from slug URLs to hashid PKs.

## Skeletons

- [Events Integration — Skeleton Bundle](skeleton_instructions.md) — context-scan bundle for integrating another app with events.

## Sub-bundles

- `Examples/` — currently empty; reserved for future events examples.
