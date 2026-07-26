---
type: "Technical Decision"
title: "Activity Thread Migration — Project Overview"
description: "Four sequential phases that move the events application from event-specific naming and a."
tags: [technical-decisions, technical-decision, project-history, activity-thread-migration-project]
context_tier: 2
---

# Activity Thread Migration — Project Overview

Four sequential phases that move the events application from event-specific naming and a
comment-only attachment model toward a shared activity-thread abstraction usable by any
domain entity.

Each phase is independently deployable (DB reset + seed between each). Each phase leaves
the codebase in a working, runnable state. Phases must be completed in order.

---

## Phase 1 — Class Name Cleanup

**What:** Generalize event-specific class and table names to domain-neutral equivalents.
Pure rename — no new columns, no new FK relationships, no logic changes.

**Scope:** Models, managers, QuerySets, domain structs, handlers, contexts. Import sites
across the codebase. Table names change (DB reset required).

**Why first:** Cleans up naming debt before schema surgery. Later phases are easier to
read and review when the class names match the domain concepts rather than the original
event-centric implementation.

→ [phase_1/](phase_1/)

---

## Phase 2 — Attachment Denormalization

**What:** Allow files to be attached directly to an event without a comment as a carrier.
`Attachment` gains a mandatory `event` FK and the `comment` FK becomes nullable.

**Scope:** `Attachment` model schema, `FileHandler`, `CommentContext.delete()`. Everything
stays pointed at `Event` — no ActivityThread concept is introduced in this phase.

**Why second:** Eliminates the machine-comment workaround for event-level file attachments.
Simplifies the upload path and makes the standalone-attachment use case first-class before
Phase 3 renames the FK target to ActivityThread.

→ [phase_2/](phase_2/)

---

## Phase 3 — Event / ActivityThread Proxy Split

**What:** Introduce `ActivityThread` as a restricted proxy alias of `Event`. Add a
`thread_type` discriminator column and behavioral flag columns to the `event` table.
Rename `Attachment.event` → `Attachment.thread` and `Comment.event` →
`Comment.activity_thread`, both pointing at the `ActivityThread` proxy. Add
`photo_gallery` and `documentation` thread FK columns to `Asset`.

**Scope:** `Event` model (new columns), new `ActivityThread` proxy model, manager
restructure, `ActivityThreadContext` thin alias, FK renames on `Comment` and `Attachment`,
`Asset` model new columns.

**Why third:** Requires Phase 2's Attachment denormalization to already be in place so
that the FK rename (event → thread) is a single targeted change rather than a schema +
logic change bundled together.

→ [phase_3/](phase_3/)

---

## Phase 4 — Presentation Layer Repair

**What:** Fix everything in the presentation layer that breaks across Phases 1–3.
Templates, entrypoints, search, admin registrations. No model changes, no control layer
changes.

**Scope:** `presentation_layer/entrypoints/`, `presentation_layer/search/`,
`presentation_layer/tools/`, `templates/`, `admin.py`.

**Why last:** The presentation layer is deliberately allowed to break during Phases 1–3 to
keep each schema/control-layer phase focused. Phase 4 is a single pass that repairs
everything at once.

→ [phase_4/](phase_4/)
