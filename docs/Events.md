---
type: "Concept Anchor"
title: "Activity Surfaces — Tier 1 Anchor"
description: "This file is the **concept anchor** for the three semantic surface classes that."
tags: [overview, concept-anchor]
context_tier: 1
---

# Activity Surfaces — Tier 1 Anchor

This file is the **concept anchor** for the three semantic surface classes that
sit over the shared `event` table. They are central to the application: nearly
every record that needs discussion or files reaches for one of them. Detail and
the underlying model live in the Tier 2 files under [applications/events/](applications/events/events.md).

---

## The one table, three classes idea

All three classes are backed by a **single physical table (`event`)**,
discriminated by a `thread_type`. There is no second table and no JOIN to read
an event. The classes are restricted aliases (Django proxy models) over that one
row shape — they add no columns. What differs between them is **behavior**, not
storage:

- whether the surface accepts **comments** (a discussion thread), and
- whether the surface accepts **files attached directly** to the row.

**Behavior is bound to the class name, not to flags a developer passes.** The
capability flags live on the row, but a developer never sets them by hand.
Choosing the class *is* choosing the behavior — instantiate `Event`,
`ActivityThread`, or `FileSet` and the correct capabilities are applied
automatically on save. This keeps the semantic name and the behavior impossible
to separate: you cannot accidentally create a "file set" that allows comments.

---

## The three classes

| Class | Use it for | Comments | Direct file attachments | Event columns (title, status, dates…) |
| :--- | :--- | :---: | :---: | :---: |
| **Event** | A real-world occurrence to track and discuss — maintenance jobs, dispatches, inventory actions. The primary record type. | ✅ | ✅ | ✅ real values |
| **ActivityThread** | A commentable record stream attached to something else — e.g. an asset's **documentation** thread, where people discuss and drop files together. | ✅ | ✅ | — sentinel-filled |
| **FileSet** | A pure collection of files with **no discussion** — e.g. an asset's **photo gallery**. A photo gallery is just a file set; the behavior drives the name. | ❌ | ✅ | — sentinel-filled |

### How they differ, in one line each

- **Event vs the other two:** an Event is a first-class occurrence with its own
  columns (title, type, status, priority, start/end). The other two borrow the
  same row shape but leave those columns sentinel-filled — they are *surfaces on*
  something, not events themselves.
- **ActivityThread vs FileSet:** both are attached surfaces, but an
  ActivityThread is a **conversation that can also hold files**, while a FileSet
  is **files only — comments are off by construction**.

### Why FileSet exists as its own class

A FileSet is behaviorally a comments-off thread, so it could in principle be "an
ActivityThread with comments disabled." It is promoted to its own class for one
reason: **construction-time safety**. Because the class forces comments off, it
is impossible to instantiate a FileSet in the wrong state, and every call site
reads its intent from the type name alone. The same applies to the photo gallery
and to any future attachments-only surface — they are all FileSets, selected by
class, never by flag.

---

## Picking a class (decision rule)

1. Does this record represent an **occurrence** with its own status/dates? → **Event**.
2. Otherwise it is a surface on another entity. Does it need **discussion**? → **ActivityThread**.
3. No discussion, **files only**? → **FileSet**.

Adding a new attachments-only surface (another kind of gallery, a document drop)
does **not** need a new class — give it a `thread_type` and let it be a FileSet.

---

## Sub-specifications

| Topic | File |
| :--- | :--- |
| Models, the shared `event` table, sentinel contract, status/priority choices, domain scoping | [applications/events/events.md](applications/events/events.md) |
| Structs and contexts that read these surfaces | [applications/events/event_context_design.md](applications/events/event_context_design.md) |
| Comment, attachment, and file lifecycle invariants | [applications/events/comment_auditing.md](applications/events/comment_auditing.md) |

---

## Reference directionality

This anchor references **only** files inside `Events/`. The capability rules
summarised above are the authoritative concept; the row-level mechanics
(sentinel fill, the shared table rationale, managers) live in the Tier 2
children so a task is answerable from this anchor plus those files.
