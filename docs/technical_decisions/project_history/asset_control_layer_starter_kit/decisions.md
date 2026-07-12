---
type: "Technical Decision"
title: "Decisions — Asset Control Layer Starter Kit"
description: "A running log of architectural decisions made while planning the migration of."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit]
context_tier: 2
---

# Decisions — Asset Control Layer Starter Kit

A running log of architectural decisions made while planning the migration of
asset/model control logic from the old Flask app (`asset_management`) into this
project's `app/assets/control_layer`. Newest decisions appended at the bottom.

---

## D1 — Creation flow: explicit orchestrator, not a pluggable pipeline

**Date:** 2026-06-02
**Status:** Accepted

**Context.** The old app wired follow-on creation work (capabilities, details,
configurations) through a **pluggable post-create pipeline**: modules registered
handler objects into `AssetContext.post_create_pipeline` at import time, and
`create()` looped them, committing each independently and swallowing failures.
The seed of the new app (`AssetHandler`) instead does its steps **explicitly in
one `transaction.atomic()` block**.

**Decision.** Asset and model creation use an **explicit orchestrator**
(`AssetCreationOrchestrator` / model equivalent) that names each follow-on step
and runs them inside a **single transaction**. Each subsystem still owns its own
`Factory`/`Handler`; only the coordination is centralized and readable. We do
**not** port the `register_post_create` registry.

**Why.** The pluggable pipeline conflicts with this project's control-layer
principles (`docs/Architecture/patterns/oop_control_patterns.md`): explicit-over-magical,
no-hidden-side-effects, one-transaction-per-workflow, and greppable tech debt.
The candidate hooks here are all first-party, so the registry's decoupling
benefit does not justify losing explicitness or transactional integrity.

**Consequence.** The creation orchestrator imports and names each downstream
step; adding a new creation side effect means editing the orchestrator (an
intentional, visible cost). Failures roll back the whole creation rather than
leaving partial state.

**Deferred alternative.** The pluggable pipeline is preserved — not deleted —
as a documented future option in the project-root file
[`optional_detail_hooking.md`](../optional_detail_hooking.md). Revisit only if we
need third-party/drop-in creation hooks the core must not know about.

---

## D2 — "FileSet" is a thread role, not a new Event proxy class

**Date:** 2026-06-03
**Status:** Accepted

**Context.** We considered a third Event alias — `FileSet` (attachments only, no
comments) — alongside `Event` (columns + comments + attachments) and
`ActivityThread` (comments + attachments), to clarify attachments-only surfaces
like an asset photo gallery.

**Decision.** Do **not** add a `FileSet` proxy class. Express the
attachments-only tier as an **`ActivityThread` with `allow_comments=False`**
(optionally under a new `FILE_SET` `thread_type` value for naming clarity).

**Why.** The capability gradient is already modeled by the two boolean flags on
`Event` (`allow_comments`, `allow_direct_attachments`) and enforced by
`ThreadPolicy.can_add_comment()` / `can_attach_directly()`. A `FileSet` proxy
would save no DB weight (identical row) and add no enforcement the flags don't
already provide; it would only add a parallel taxonomy competing with
`thread_type`. A proxy earns its keep only with a distinct FK target or a
save-time invariant — `FileSet` needs neither.

**Consequence.** One non-event proxy (`ActivityThread`) covers both
"comments+attachments" and "attachments-only," selected by flags + `thread_type`.

**Detail / per-model usage.** See
[`events and Activity Thread useage.md`](events%20and%20Activity%20Thread%20useage.md),
which also flags the `Asset.photo_gallery` ↔ `AssetImage` overlap to resolve in
P1/P2. **To reverse:** add a `FileSet(Event)` proxy mirroring
`activity_thread_proxy.py` with its own manager and an `allow_comments=False`
save invariant.

> **Superseded by D3 (2026-06-03).** We took the "To reverse" path: `FileSet` is
> now a real proxy class.

---

## D3 — `FileSet` promoted to a third surface proxy; behavior bound to class, not flags

**Date:** 2026-06-03
**Status:** Accepted (supersedes D2)

**Context.** D2 rejected `FileSet` on a *DB-weight / enforcement-parity* basis —
the flags already model the gradient, so a proxy saved nothing. That reasoning
held for storage but ignored **construction safety**: with only flags, every
caller must remember `allow_comments=False, allow_direct_attachments=True`, and a
typo silently produces a commentable "gallery."

**Decision.** Introduce three semantic surface classes over the shared `event`
table — `Event`, `ActivityThread`, `FileSet` — and **bind behavior to the class,
not to caller-passed flags**. `Event.save()` forces each class's `thread_type`
family and capability flags from class-level attributes; callers no longer pass
flags anywhere. Each proxy owns a **disjoint** `thread_type` family via
`FamilyThreadManager`, so managers never leak across surfaces. `Asset.photo_gallery`
retargets to `FileSet` — a photo gallery *is* a file set; the behavior drives the
name.

**Why.** This satisfies D2's own stated reversal trigger — a **save-time
invariant** (`allow_comments=False` forced for FileSet) — and is justified by ≥2
planned attachments-only surfaces. It makes the semantic name and behavior
inseparable: a wrongly-configured FileSet is now impossible to construct.

**Consequence.** Adding an attachments-only surface needs only a new `thread_type`
added to `FileSet._THREAD_TYPES` — no new class, no flag wiring. Capability flags
remain on the row for the policy layer to read, but are no longer a caller input.
Concept doc: [docs/Activity_Surfaces.md](../docs/Activity_Surfaces.md) (Tier 1).

---

## D4 — "Details" recast as a first-party **plugin framework**; supersedes the Phase 2 detail design

**Date:** 2026-06-04
**Status:** Accepted (supersedes the original Phase 2 "Asset & Model Details" plan)

**Context.** The original Phase 2 modeled a fixed set of concrete detail tables
(`PurchaseInfo`, `VehicleRegistration`, `SmogRecord`, `ModelInfo`, `EmissionsInfo`)
hard-wired behind a `DETAIL_TYPE_REGISTRY` string→model map and provisioned by
detail factories. That shape treats each detail as a passive field bag the asset
code knows about by name. The actual intent is an **extendable system**: each
"detail" is a self-contained unit (its own table, its own provisioning rule, and
later its own card and behavior) that can be **added without reshaping the host**,
and configured per asset class and per model the way the old Flask app did.

**Decision.** Replace "details" with an **asset plugin framework**. A *plugin* is a
package under `app/assets/plugins/<plugin_name>/` that owns: a **primary typed
table**, a **descriptor** declaring its contract, and a **factory** that
provisions its row(s). The host (`Asset` / `AssetModel`) never imports a plugin's
model — it discovers enabled plugins through enablement tables and an explicit
registry, then calls each plugin's factory. Phase 2 is split:
**2a — plugin framework** (contract, registry, factory seam, provisioning hook,
managers, union struct, proven with two reference plugins) and
**2b — first-party plugins** (port the remaining concrete details onto the seam).

**Why.** All candidate plugins are first-party, so we keep the *explicit* spirit of
[D1](#d1--creation-flow-explicit-orchestrator-not-a-pluggable-pipeline): discovery
is an **explicit registry list**, not import-time self-registration, and the
on-create hook is still a named step inside `AssetCreationOrchestrator`'s single
transaction. The framework adds the extension seam the original plan lacked while
preserving transactional integrity and greppability.

**Consequence.** Adding a new detail type becomes: create a plugin package
(table + descriptor + factory), register it in one explicit list, and enable it on
a class/model — **no edit to host models or the orchestrator body**. The minimum
plugin contract is **target** (asset vs. model) + **cardinality** (one-to-one vs.
one-to-many); rules, derived status, and the asset-page card are **deferred** (the
descriptor and factory reserve room for them). UI is out of scope for this kit.

**Naming.** `detail` → `plugin` throughout. Template tables renamed:
`asset_plugins_by_asset_class`, `asset_plugins_by_model`,
`model_plugins_by_asset_class`. The `detail_table_type` string → `plugin_key`. The
`Asset.detail_rows_created` marker → `plugins_provisioned` (and a matching marker
is added to `AssetModel`).

---

## D5 — Cardinality lives on the plugin descriptor, not on the enablement row

**Date:** 2026-06-04
**Status:** Accepted

**Context.** The old template rows carried `many_to_one` per row, so the same
detail type could be single in one class and repeating in another. With plugins,
whether a plugin is a single record (current registration) or a history (every
smog test) is intrinsic to **what the plugin is**, not to where it is enabled.

**Decision.** **Cardinality is a class-level attribute on the plugin descriptor**
(`ONE_TO_ONE` / `ONE_TO_MANY`), read by the manager when enforcing `add()`. The
enablement tables drop `many_to_one` and carry only `(scope_fk, plugin_key)`.

**Why.** Binds behavior to the plugin (mirrors [D3](#d3--fileset-promoted-to-a-third-surface-proxy-behavior-bound-to-class-not-flags)'s
"behavior bound to the class, not caller flags"): a plugin can't be accidentally
made repeating in one place and single in another. Enablement rows become pure
on/off switches, which is all the per-class/per-model config needs.

**Consequence.** Reusing one plugin with two different cardinalities (rare) would
require two plugin packages. Acceptable given none of the ported details need it.

**Model-plugin scope.** Model plugins are enabled **by asset class**
(`model_plugins_by_asset_class`), not per individual model — a deliberate
simplification of the old per-model `ModelDetailTableTemplate`. Per-model model
plugins can be added later as a second enablement table if a model ever needs
specs no sibling model in its class shares.

---

## D6 — Asset↔Event link: `AssetEvent` join accepted; flag a future denormalization plan

**Date:** 2026-06-04
**Status:** Accepted (with a deferred follow-up)

**Context.** Phase 1 links assets to lifecycle events through an `AssetEvent`
**join table** (`unique(asset, event)`), rather than a direct `asset_id` FK on the
`event` table. The join keeps the events app generic/domain-scoped and supports a
**many-to-many** future (multiple assets per event — e.g. one event spanning a
parent and its children, or a shared maintenance action).

**Decision.** Keep the `AssetEvent` join table. It is the right relational shape
for "multiple assets per event," which is an anticipated requirement.

**Deferred follow-up — performance denormalization.** The join adds a hop on every
"events for this asset" read. If event volume makes that hop expensive, we may want
to **denormalize a nullable `asset_id` (or a primary-asset pointer) directly onto
the `event` table** as a read accelerator, kept in sync alongside `AssetEvent`
(the join stays authoritative for the M2M). **Action item:** before adopting this,
write a short plan covering — which read paths justify it, how the denormalized
column stays consistent with `AssetEvent` (single-writer through the control
layer), what "primary asset" means when an event has several, and the blast radius
on the events app. Do **not** add the column ad hoc; it needs the plan first.

**Why deferred.** Denormalizing now would prematurely bias the link toward
one-asset-per-event and couple the events table to assets before we have a measured
read-performance problem. The join is correct and cheap to start; the accelerator
is a later, measured optimization.

---

## D7 — `plugin` → `extension`; extensions become a separate app with an inverted dependency

**Date:** 2026-06-06
**Status:** Accepted (supersedes D4's naming and packaging; D4's framework *concept* stands)

**Context.** D4 introduced the framework as "plugins" inside the assets app
(`app/assets/plugins/`), with the orchestrator importing plugin factories and the
concrete tables registered through `assets/models/__init__.py`. Two problems
surfaced: (a) the units are growing their own interactive pages/cards
(`assets/<id>/extensions/<name>`), so they extend the asset's **surface**, not just
its data — "extension" fits better than "plugin"; (b) housing them in assets and
importing concrete tables in `models/__init__.py` makes **assets depend on every
plugin**, the opposite of the goal — assets must stay ignorant of what extends it.

**Decision.** Rename `plugin` → `extension` throughout, and move the whole framework
into a new app `app/asset_extensions/`. The dependency points **one way only**:
`asset_extensions → assets` (via FKs). Assets gains **zero** compile-time knowledge
of extensions.

- The three **enablement tables move out of assets** into `asset_extensions` — assets
  no longer reads them (provisioning leaves the orchestrator; see [D8](#d8)).
- The **concrete extension tables** (`EmissionsInfo`, `ModelInfo`, `PurchaseInfo`,
  `SmogRecord`, `VehicleRegistration`) leave `assets/models/__init__.py` and register
  under the `asset_extensions` app.
- The **registry stays a `.py` manifest** (greppable, typed, no `importlib` magic per
  D1) but lives in `asset_extensions`, not assets.
- `…TableVirtual` abstract bases → `…TableContract` (still `abstract`); the
  virtual/abstract-table nature is kept.

**Registry vs enablement.** Kept distinct: the **registry** is the *code manifest*
("which extensions exist in the codebase") and stays code; **enablement** is *data*
("which extensions apply to which class/model") and stays DB tables. JSON was
rejected — it blurs the two and forces dynamic imports.

**Naming.** `plugin` → `extension` everywhere: `plugin_key` → `extension_key`;
`plugins_provisioned` → `extensions_provisioned` (on `Asset` and `AssetModel`); tables
`asset_plugins_by_asset_class` → `asset_extensions_by_asset_class`,
`asset_plugins_by_model` → `asset_extensions_by_model`,
`model_plugins_by_asset_class` → `model_extensions_by_asset_class`. `AssetPlugin`
descriptor → `AssetExtension`; `PluginFactory` → `ExtensionFactory`;
`AssetPluginTableVirtual` / `ModelPluginTableVirtual` → `AssetExtensionTableContract`
/ `ModelExtensionTableContract`; `*PluginsManager` → `*ExtensionsManager`.

**Display.** The asset 360 page never imports an extension. It HTMX-includes a panel
by URL (`/asset_extensions/<asset_id>/?format=htmx-panel`); each card links to the
extension's own sub-page (`/asset_extensions/<asset_id>/<extension_key>/?format=large`).
Adding an extension makes a new card appear with **no edit to assets**. Uses the
existing `format=` contract, not a bespoke query param.

**Consequence.** Assets ↔ extensions touch at exactly two seams: a **signal** assets
emits ([D8](#d8)) and **URL strings** in templates. Concrete extensions can later
graduate to their own Django apps if any needs independent deployment; the
vertical-slice layout inside `asset_extensions/` anticipates that.

---

## D8 — Extension provisioning is signal-driven and post-commit (eventual); narrows D1 for the extension step only

**Date:** 2026-06-06
**Status:** Accepted (narrows [D1](#d1--creation-flow-explicit-orchestrator-not-a-pluggable-pipeline) for the extension step)

**Context.** D1 chose an explicit orchestrator over a pluggable/signal pipeline for
the whole create flow, to keep one transaction and greppability. But D7 requires
assets to **not** depend on extensions, which an orchestrator that imports extension
factories violates. The orchestrator cannot both name the extension step and stay
ignorant of extensions.

**Decision.** Remove the extension-provisioning step from `AssetCreationOrchestrator`
/ model creation. Assets instead defines and emits domain signals — `asset_created`,
`asset_model_created` (in `app/assets/signals.py`) — as the **last in-transaction
step** of creation. The `asset_extensions` app connects a receiver (registered in
`asset_extensions/apps.py` `ready()`) that provisions via `transaction.on_commit`:
the asset **commits first**, then extension rows are created in a **separate
transaction** (eventual consistency). D1's explicit-orchestrator stance still governs
every **other** create step (meter, tree, eventing, capabilities, configurations) —
only extensions move to the signal.

**Why eventual** (not atomic / lazy). Chosen on the consistency ↔ independence
spectrum: a broken extension must **never** block creating an asset, and an asset is
valid standalone. Post-commit provisioning guarantees the asset always commits;
extension rows follow.

**Safety net.** Provisioning stays **idempotent** via the `extensions_provisioned`
markers (D4): the post-commit receiver, a re-run, or a backfill fill newly-enabled or
missed extensions without duplicating. This makes the temporary "asset exists,
extensions not yet provisioned" window safe — any reader must tolerate it, and any
gap self-heals.

**Consequence.** *Lost* vs D1: single-transaction integrity for extensions, and the
one-file greppability of "what happens on asset create" (now one documented receiver,
not a named orchestrator step). *Gained:* assets stays fully independent of
extensions. The signal is **load-bearing** (it triggers provisioning), unlike the
lazy alternative where it would be a mere pre-warm.
