# Phase 1 — Internal Parts (the engineering core)

## Goal

Stand up the new `app/parts/` sub-app and the **Part** hub — the canonical "base part id" the
rest of the application references — together with its **flat linear revision history** and
**revision-attached documents** (via the events file system). Prove the whole engineering core
headless, with **zero supplier coupling**.

## In scope

- New sub-app `app/parts/` with the standard layered structure.
- `Part` table (the base id + canonical internal `part_number`).
- `PartRevision` table — numeric major/minor model, "current = highest `(major, minor)`"
  ([D4](../decisions.md)).
- **Comments + documents** on the Part and on each revision via the events
  `ActivityThread`/`Comment`/`Attachment`/`File` system ([D5](../decisions.md)).
- Control layer: `PartContext`, `PartStruct`, `PartRevisionStruct`, `PartFactory`,
  `PartRevisionManager`, `PartThreadManager`, `PartRevisionNarrator`.
- The `seed_dev` contribution (see "Seed data" below).

## Out of scope

- Anything supplier-side (manufacturers, supplier items) — Phase 2.
- Aliases / unified search — Phase 3.
- UI — Phase 4. (Phase 1 is validated headless / via shell + tests.)
- RBAC gating, release/approval state machine (provisional defaults only — see OQ5/OQ6).

## Dependencies

- Existing `events` file system (`File`, `Attachment`, `FileSet`, `FileHandler`) — see
  [`../existing_seams_audit.md`](../existing_seams_audit.md).
- **Blocking decision: OQ1** (how a revision binds to its FileSet) must be confirmed before the
  document step is implemented. Tables and revision logic can be built ahead of that.

## Deliverables

- [ ] `app/parts/` created with layered folders and registered in settings/urls.
- [ ] `Part` and `PartRevision` models with audit columns and the `sequence`/`status` design.
- [ ] `PartStruct` + `PartRevisionStruct` read models with `to_dict()`.
- [ ] `PartContext` entry point with `current_revision`, `revisions`, `documents`, `comments`.
- [ ] `PartFactory.create()` — creates a Part and its base revision (`major=1, minor=0, DRAFT`).
- [ ] `PartRevisionManager` — `release_major`, `redline`, `set_status`.
- [ ] `PartThreadManager` — attach/detach documents and add comments via the events thread.
- [ ] `PartRevisionNarrator` for human-readable revision/status strings.
- [ ] Seed data (below); full DB reset via `/db-rebuild`.

## Exit criteria

- [ ] A Part can be created end-to-end through `PartContext` / `PartFactory` in one transaction,
      yielding a Part with a base revision (`major=1, minor=0`).
- [ ] `release_major` allocates the next major at `minor=0`; `redline` allocates the next minor
      under its major. `PartContext.current_revision` returns the highest `(major, minor)` row —
      **not** the highest `sequence`.
- [ ] A redline issued against an **older** major (after a newer major exists) gets a later
      `sequence`/`date_of_release` but does **not** become current.
- [ ] A document attached — and a comment added — to a specific revision is readable via
      `PartContext.documents(rev)` / `.comments(rev)`, and does **not** appear on another revision.
      Part-level comments/documents work on the Part's own thread.
- [ ] Nothing in `app/parts/` imports or references any supplier concept (verifiable by grep).
- [ ] The base Part id is the only handle a hypothetical consumer needs — a read returns a full
      `PartStruct` from an id alone.

## Seed data

`seed_dev` contribution (full spec in [`../open_questions.md`](../open_questions.md) → Seed plan):

- **16 Parts** total. Four **car-part drivers** fully exercised — **alternator, engine, starter,
  AC compressor** — with **varied revision depth** (different major counts + redlines, including a
  redline on an *older* major to prove the "current" rule). A few drawings/comments on selected
  revisions. The other 12 parts are light (1–2 revisions).
- Manufacturers, supplier items, and aliases for the drivers are seeded in Phases 2–3.
