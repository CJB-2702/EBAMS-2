# Brainstorming Session — 2026-06-03

Session that produced this starter kit. Captures the goal, what was investigated,
the decisions reached, and what was built. A human-readable companion to
[`decisions.md`](decisions.md) and [`initial_prompt.md`](initial_prompt.md).

## Goal

Migrate asset/model **control logic** from the old Flask app
(`/home/cb/REPOS/asset_management`, `app/business/{core,assets}`) into this
Django project's `app/assets/control_layer`, rebuilt to this repo's layered
architecture. Verbatim prompt preserved in [`initial_prompt.md`](initial_prompt.md).

## How the session ran

1. **Architecture contrast first.** Read both codebases' architecture docs and
   key source. Established this is two changes at once: a **framework port**
   (Flask/SQLAlchemy → Django ORM) and a **domain remodel**.
2. **Interrogation.** Asked four scoping questions; the answers reshaped the work
   from "write code" into "build a phased planning kit + settle architecture
   decisions."
3. **Two architecture chats** (create-flow, then the FileSet alias) resolved into
   recorded decisions D1 and D2.
4. **Built the kit** — overarching docs + four phase sub-kits.
5. **Added** the Events/ActivityThread usage doc and the per-model outline.

## Key facts established

- The new Django **models are already built** (`app/assets/models/`: core,
  capabilities, configurations, details, domain_junctions). The **control layer**
  is what's missing — only `asset_handler.py` existed.
- The new **`events` app is already richly built** (handlers, contexts, comment
  shadow/machine-comment machinery, policies, structs, search). The old
  `EventContext` is therefore **superseded**, not ported.
- The new `AssetManagementDetail` model **explicitly reserves** the asset↔event
  link for `app/assets` — the migration must add that link (`AssetEvent`).

## Domain remodel (old → new)

| Old | New |
| :--- | :--- |
| `MajorLocation` (access control) | **`Domain`** (data domains) + junctions |
| `MakeModel` (make/model/year) | **`AssetModel`** (model_name/subtype/revision tree) + extracted **`Manufacturer`** |
| asset class / model / asset in **`core`** | in the **`assets`** app |
| single `Event` with `asset_id` | generic `Event` + `ActivityThread` proxy; asset link reserved for assets app |
| asset_class via make_model at read time | **denormalized `Asset.asset_class`** kept in sync by a propagation handler |

## Decisions reached

- **D1 — Explicit orchestrator, not a pluggable pipeline.** Creation fans out via
  a named `AssetCreationOrchestrator` in one `transaction.atomic()`, not the old
  import-time `register_post_create` registry. Rejected alternative preserved at
  project-root [`../optional_detail_hooking.md`](../optional_detail_hooking.md).
- **D2 — "FileSet" is a thread role, not a new Event proxy class.**
  Attachments-only = `ActivityThread(allow_comments=False)` (optionally a
  `FILE_SET` `thread_type`). The two boolean flags + `ThreadPolicy` already model
  and enforce the gradient; a proxy would save no weight and add no enforcement.
- **Eventing** is wired into the existing `events` app (extended only if a
  "system/already-complete" create path proves necessary), not stubbed.
- **Scope** = asset + AssetModel control logic. Event/user/role logic from old
  `business/core`, and `technical_library`, are **out of scope** for `assets`.

## Phase order chosen (and why)

**P1 asset+model contexts → P2 details → P3 configurations → P4 capabilities.**
P1 builds the seams everything plugs into (orchestrator + eventing). P2 is the
simplest consumer of that seam. P3 is mostly self-contained assignment logic. P4
last because it has the heaviest copy-on-create cascade and benefits from a
settled orchestrator.

## Open questions carried into implementation

1. **`AssetEvent` link shape** — join table in `app/assets` (recommended) vs. a
   field on `AssetManagementDetail`. Adding it triggers `/db-rebuild`.
2. **Transaction boundary** for lifecycle events — inside the asset's atomic block
   (recommended) vs. nested via `EventHandler.create`.
3. **Does `EventHandler` need a "system/already-complete" path?** The only likely
   change to the events app.
4. **`Asset.photo_gallery` (thread) ↔ `AssetImage` (FK to events.File) overlap** —
   pick one image write path in P1/P2; don't build both.
5. **Capability cascade specifics** — copy all vs. subset; inactive handling;
   exact `capability_status` formula (confirm against old source).
6. **Config templates auto-instantiating child assets?** Default: no (track
   expected vs. actual only).

## Artifacts produced

```
asset_control_layer_starter_kit/
├── README.md                          # index, build order, how-to
├── initial_prompt.md                  # verbatim prompt + clarifying answers
├── decisions.md                       # D1, D2
├── architecture_contrast.md           # framework port + domain remodel + checklist
├── event_context_study.md             # old EventContext vs new events app; the link to add
├── events and Activity Thread useage.md  # gradient + per-model thread/event outline (D2)
├── migration_map.md                   # every old file → new home / superseded / out-of-scope
├── brainstorming_session_20260603.md  # this file
├── phase_1_asset_and_model_contexts/  # README + business_concept + data_relational + control_layer + old_to_new
├── phase_2_asset_and_model_details/   #   "
├── phase_3_configurations/            #   "
└── phase_4_capabilities/              #   "
../optional_detail_hooking.md          # rejected pipeline alternative (project root)
```

## Status

Planning only — **no application code written, no schema changed.** Next concrete
step when implementation begins: Phase 1, starting by settling the `AssetEvent`
link shape (open question 1).
