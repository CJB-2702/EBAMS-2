# Asset Relationships Starter Kit

Build a first-class **parent ⇄ child relationship** capability for assets: a dedicated
relationship manager, a tree struct that materializes the hierarchy to any depth, an
auditable Event on every attach/detach, and a view/edit UI reached from **Configurations →
Asset Relationships**.

## Why this kit exists

The schema seam already exists — `Asset.parent_asset`, `Asset.root_asset`,
`Asset.depth_from_root` are live columns, and `AssetHierarchyManager.reparent()` /
`AssetHierarchyStruct` already move and read a single hop. What is **missing** is:

1. A **dedicated, intention-revealing manager** for parent/child operations
   (`attach_child` / `detach_child` / bulk attach), not just a low-level `reparent`.
2. An **Event** on every relationship change, referencing **both** the parent and the
   child — today only a structured `AssetParentHistory` row is written, nothing surfaces
   on either asset's timeline.
3. A **correct subtree cascade** — `reparent()` currently updates only the moved node's
   `root`/`depth`, leaving its descendants stale.
4. A **UI surface** — view and edit a node's children with progressive depth expansion and
   search-to-attach.

This kit does **not** add database columns or tables. Every persistence seam it needs
(`parent_asset`, `root_asset`, `depth_from_root`, `AssetParentHistory`, `AssetEvent` with
its `role` field) already exists. See [`existing_seams_audit.md`](existing_seams_audit.md).

## Phases

| Phase | Folder | Goal |
| :--- | :--- | :--- |
| 1 | [`phase_1_relationship_control_layer/`](phase_1_relationship_control_layer/) | A dedicated `AssetRelationshipManager` + `AssetTreeStruct`; every attach/detach emits a dual-linked Event; the subtree cascade is correct. **No UI, no new tables.** |
| 2 | [`phase_2_relationship_ui/`](phase_2_relationship_ui/) | The **Asset Relationships** Configurations entry; the `children/view` and `children/edit` pages; HTMX depth-on-click expansion; search-to-attach. |

### Why this order

Phase 1 builds the only seam Phase 2 plugs into: a manager whose `attach_child` /
`detach_child` the edit page calls, and a tree struct the view/edit pages render. The UI is
a thin shell over a control layer that must already be transactionally correct (cycles,
cascade, eventing) before any button is wired. Phase 1 is fully testable headless; Phase 2
is fully testable in the browser.

## How to use a phase sub-kit

Each `phase_N_*/` folder is self-contained:

- `README.md` — goal, in/out of scope, dependencies, deliverables, **exit criteria checklist**.
- `business_concept.md` — what the phase delivers in user language.
- `data_relational_plan.md` — tables touched (Phase 1 touches none new).
- `control_layer_plan.md` — Structs / Contexts / Managers / Narrators and the delegation flow.
- `ui_features_plan.md` — (Phase 2) page inventory, classifications, HTMX contracts.

Read the root [`decisions.md`](decisions.md) first — it records the design choices both
phases assume.

## Root documents

| File | Purpose |
| :--- | :--- |
| [`initial_prompt.md`](initial_prompt.md) | Verbatim request + clarifying decisions captured during interrogation. |
| [`decisions.md`](decisions.md) | Architectural decision log (D1–D8). |
| [`existing_seams_audit.md`](existing_seams_audit.md) | What already exists in the codebase vs. what this kit adds — the audit that reframed the work. |
| [`brainstorming_session_20260619.md`](brainstorming_session_20260619.md) | Narrative of the session that produced this kit. |
