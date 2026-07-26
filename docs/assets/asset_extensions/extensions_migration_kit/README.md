# Extensions Migration Kit

Pre-implementation planning kit for **relocating the existing asset plugin
framework out of `app/assets/` into a new standalone app `app/detail_extensions/`**,
renaming `plugin → extension` throughout, and **inverting the dependency** so the
assets app no longer knows extensions exist.

**This kit is documentation, not code.** It follows the methodology in
[`harness/starter_kit_process`](../harness/starter_kit_process/). The originating design
is recorded in the sibling kit's decisions —
[`asset_control_layer_starter_kit/decisions.md`](../asset_control_layer_starter_kit/decisions.md)
**D7** (rename + separate app + inverted dependency) and **D8** (signal-driven,
post-commit provisioning).

> **This is a refactor of working code, not a greenfield build.** The framework is
> already fully wired in place: `app/assets/plugins/` (descriptor, registry,
> factory, enablement, table bases, 5 concrete plugins) **plus** a complete control
> layer (`app/assets/control_layer/plugins/`: provisioners, managers, structs,
> registry guard), `AssetContext.plugins` / `AssetModelContext.plugins`, orchestrator
> wiring, and mock display/config entrypoints. There is **no production data** — dev
> uses a full DB rebuild — so the "migration" is a code move + rename + rewire, not a
> data migration. [`migration_map.md`](migration_map.md) is the spine: every existing
> file → its new home or "deleted".

## Read these first (kit root)

| Doc | Purpose |
| :--- | :--- |
| [`initial_prompt.md`](initial_prompt.md) | The originating request + clarifying decisions captured during interrogation. |
| [`decisions.md`](decisions.md) | Architectural decision log for this migration (E1–E8), building on the sibling kit's D7/D8. |
| [`brainstorming_session_20260606.md`](brainstorming_session_20260606.md) | Narrative of the session that produced this kit. |
| [`migration_map.md`](migration_map.md) | Every existing plugin file → new home / renamed / deleted. The execution spine. |

## Phases (build in this order)

| Phase | Folder | Scope |
| :--- | :--- | :--- |
| **1** | [`phase_1_app_relocation/`](phase_1_app_relocation/) | Stand up `app/detail_extensions/`. Move the framework (descriptor, registry, factory, table contracts), the 3 enablement tables, and the 5 concrete extensions into **vertical-slice packages each carrying a file manifest**. Rename `plugin → extension`. Delete the old packages. The assets orchestrator may **still** call the relocated provisioner this phase (transient import, severed in P2). |
| **2** | [`phase_2_signal_inversion/`](phase_2_signal_inversion/) | Invert the one dependency edge. Add `app/assets/signals.py` (`asset_created`, `asset_model_created`); assets emits, `detail_extensions` listens and provisions via `transaction.on_commit`. Move the `.plugins` managers/structs **off** the asset contexts. Move provisioning state **off** the asset tables into `detail_extensions`. Remove every extension import from assets. |
| **3** | [`phase_3_configuration_ui/`](phase_3_configuration_ui/) | Real assignment/configuration UI under `/detail_extensions/configuration/` (CRUD on the enablement tables — replaces the current mock). Define the per-extension URL grammar + the aggregate 360-panel as a **documented interface contract + base routing scaffolding** (page bodies for individual extensions are **out of scope**). |

Each phase folder has its own `README.md` with goal, in/out of scope, dependencies,
deliverables, and an exit-criteria checklist.

## Why this order

1. **P1 relocates *code* before changing *behavior*.** Moving and renaming is a
   mechanical, compile-and-rebuild checkpoint. A transient `assets → detail_extensions`
   import is tolerated so the project keeps booting while the files move.

2. **P2 flips the single dependency edge in isolation.** With the code already in
   place, "assets is now ignorant of extensions" becomes one focused, independently
   verifiable change: `grep -r detail_extensions app/assets` returns zero imports.
   Severing the marker column and the `.plugins` context properties happens here
   because that is the moment the ignorance guarantee must hold.

3. **P3 is purely additive UI on a settled seam.** The config UI and the extension
   route grammar sit on top of stable models and a stable provisioning flow.

## How to use a phase sub-kit

1. Read the phase `README.md` for scope + exit criteria.
2. Read `business_concept.md` (what it delivers), then `data_relational_plan.md`
   (tables touched), then `control_layer_plan.md` (Structs/Contexts/Managers/
   Handlers/Guards named per [`oop_control_patterns`](../harness/Architecture/OOP_CONTROL_PATTERNS.md)).
   Phase 3 adds `ui_features_plan.md`.
3. Use `old_to_new_migration.md` as the per-file porting checklist.
4. After any schema change, **full DB rebuild** (`/db-rebuild`) — never incremental
   migrations (project rule).
