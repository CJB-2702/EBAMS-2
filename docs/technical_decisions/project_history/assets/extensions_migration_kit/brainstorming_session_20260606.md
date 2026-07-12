# Brainstorming Session — 2026-06-06

## Goal

Decide whether the existing asset "plugin" framework should be renamed, relocated, and
decoupled from the assets app — and if so, capture the design as an executable kit.

## How the session ran

Started from a review of `phase_2a_plugin_framework/README.md`. The owner's instinct
was that "plugin" undersold what these units are becoming: each one is growing its own
interactive pages, so it **extends the asset's surface**, not just its data. That
reframing — from "passive data attachment provisioned at create time" to "self-contained
feature module with its own presentation" — drove every subsequent decision.

We worked three axes:

1. **Terminology** — `plugin → extension`. Settled on the app name `detail_extensions`
   because the units extend *both* assets and asset models ("extended details").
2. **Physical placement** — the concrete tables (`EmissionsInfo`, etc.) leave the
   assets app entirely; the enablement/assignment tables move with them. The line in
   `assets/models/__init__.py` that imports every concrete table was identified as the
   real boundary leak.
3. **Dependency direction** — the crux. The owner wants assets to **not depend on**
   extensions: emit a signal, let extensions react. We walked the three FK/provisioning/
   display directions and confirmed only provisioning and display needed inverting (FKs
   already point the right way: `extensions → assets`).

For provisioning we compared three consistency levels — **atomic** (in the create
transaction), **eventual** (post-commit), **lazy** (on first access) — and the owner
chose **eventual**: a broken extension must never block creating an asset.

## Key facts established

- The framework is **already built and wired**, not a stub: descriptor, registry,
  factory, table bases, 5 concrete plugins, full control layer (provisioners, managers,
  structs, guard), context properties, orchestrator wiring, and **mock** display/config
  entrypoints.
- There is **no production data**; dev rebuilds the DB. The migration is a code
  move + rename + rewire, not a data migration.
- The current config/display entrypoints are mock ("not persisted") — Phase 3 makes
  them real.

## Decisions reached

Recorded as **E1–E8** in [`decisions.md`](decisions.md), executing **D7/D8** from the
sibling kit. Headlines: new app `detail_extensions` (E1); clean cut, no shims (E2);
signal-driven post-commit provisioning with the `Signal` defined in `assets` (E3);
central framework control (E4); per-extension file manifest (E5); config UI + route
contract, per-extension bodies deferred (E6); provisioning state moved off the assets
tables (E7); canonical names (E8).

## Phase shape

Three phases: **P1** relocate + rename (clean cut, transient import allowed); **P2**
invert the dependency via signals + move provisioning state off assets; **P3** config
UI + extension route-pattern contract.

## Open questions carried into implementation

- **Manifest enforcement strength** — does an incomplete `ExtensionManifest` fail at
  startup (hard) or only warn? Leaning hard-fail to match the registry guard's
  unknown-key behavior; confirm when building E5.
- **Signal emission point precision** — `asset_created` must fire *after* meter/tree/
  eventing in the orchestrator, not on Django `post_save` (which fires too early).
  Verify the orchestrator's final-step ordering during P2.
- **Aggregate panel ownership** — the 360-panel route lists *all* enabled extensions
  for one owner; confirm it lives at `/detail_extensions/<asset|model>/<id>/` and does
  not collide with the per-extension `<extension-key>` segment (it won't — owner-type
  vs extension-key occupy different first segments, but the resolver must disambiguate).
- **Model-target search/summary semantics** — for `target=MODEL` extensions the
  `<assets|models>` segment resolves to `models`; confirm copy/labels in P3.
