# Design Context — Attachment Architecture Evolution

This document records the design positions considered for attaching files and comments to
events. It is reference material explaining *why* the phased approach was chosen — not a
build specification.

For build specifications see:
- Phase 2 (Attachment denormalization, Event FK): [phase_2/](phase_2/)
- Phase 3 (ActivityThread proxy, FK retarget): [phase_3/](phase_3/)

---

## 1. Original architecture — flat per-event tables

Attachments lived on `Comment` only. Files could not be attached directly to an event.
A "machine comment" was used as a carrier for event-level files.

```
Event
  └── Comment    (FK → Event)
        └── Attachment  (FK → Comment, mandatory)
```

**Problems:**
- No standalone event attachments — every file needed a comment carrier
- Deleting a comment triggered an orphan-file check and potential file deletion
- The file timeline mixed human comments with machine-generated comment carriers

---

## 2. Attempted — full normalisation with a join model

A dedicated `Item` join model was introduced to give attachments and comments a shared
anchor independent of entity type.

```
Attachment → Comment → Item
ItemAttachment → Item
```

**Why this failed:**
- Every write path required registering an `Item` row (hidden cascade)
- Two unrelated trees (`Comment → Item` and `ItemAttachment → Item`) were hard to order
  into a coherent feed
- Django generic relations (ContentType) added query overhead and obscured intent
- Conflicted with the proxy model approach used in Phase 3

---

## 3. Phase 2 compromise — Attachment gets a direct Event FK

Attachment gains a mandatory `event` FK. The `comment` FK becomes nullable. No join model.
No ActivityThread concept.

```
Event
  ├── Comment       (FK → Event)
  │     └── Attachment (optional: FK comment → Comment)
  └── Attachment    (standalone: comment = NULL, FK event → Event)
```

This is the Phase 2 end-state. Standalone attachments are first-class.
See [phase_2/model_changes.md](phase_2/model_changes.md).

---

## 4. Phase 3 — FK retargeted to ActivityThread proxy

The `event` FK on `Attachment` (and `Comment`) is renamed to `thread` / `activity_thread`
and retargeted to the `ActivityThread` proxy. The proxy shares the `event` table — there
are no new physical tables.

```
ActivityThread  (proxy of Event — same table, same PK)
  ├── Comment       (FK activity_thread → event.id)
  └── Attachment    (FK thread → event.id, comment nullable)

Asset
  ├── photo_gallery  → ActivityThread
  └── documentation  → ActivityThread
```

See [phase_3/model_changes.md](phase_3/model_changes.md).
