# Modification Applicability Kit
Created 2026/06/09

Pre-implementation planning kit for giving **modifications** and **configuration
templates** their own rules about *where they may be applied* — so the system can
refuse to put an engine modification on a laptop.

**This kit is documentation, not code.** It follows the methodology in
[`docs/starter_kit_process`](../docs/starter_kit_process/). Scope is deliberately
narrow: **models + control layer only**. Screens are noted where they will eventually
attach but are **out of scope** here (see [D9](decisions.md)).

## The core idea in one paragraph

A `DefinedModification` (and a `ConfigurationTemplate`, which is just a named group of
modifications) carries an **applicability mode** plus two allow-lists: a set of asset
**classes** and a set of asset **models**. When something is applied to a real asset,
the asset's class/model is checked against those lists according to the mode. The mode
decides whether the check is a hard gate or just a search/suggestion hint. The full
truth table lives in
[`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md)
— **read that first**, it is the semantic heart of the kit.

## Read these first (kit root)

| Doc | Purpose |
| :--- | :--- |
| [`initial_prompt.md`](initial_prompt.md) | The originating request + clarifying decisions captured during interrogation. |
| [`decisions.md`](decisions.md) | Architectural decision log (D1–D10) — the *why* behind every choice. |
| [`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md) | **The matrix.** The four modes, the AND rule, auto-derive, dead-model guard, worked examples. |
| [`guard_and_checkpoint_map.md`](guard_and_checkpoint_map.md) | Every relationship in the chain and the guard/checkpoint that fires at each — the "guard as early as possible" map. |
| [`brainstorming_session_20260608.md`](brainstorming_session_20260608.md) | Narrative of the session that produced this kit. |
| [`conversation_summary_20260609.md`](conversation_summary_20260609.md) | Chronological summary of the session: what was asked, how the design converged, decisions made on the user's behalf. |

## Phases (build in this order)

| Phase | Folder | Scope |
| :--- | :--- | :--- |
| **1** | [`phase_1_modification_applicability/`](phase_1_modification_applicability/) | Give `DefinedModification` an `applicability_mode` + the `modification_asset_class` / `modification_model` allow-lists. Build the **shared** `ApplicabilityPolicy` + `ApplicabilitySyncHandler` here and prove them on the simpler entity. Gate `add_actual_modification`. |
| **2** | [`phase_2_template_applicability/`](phase_2_template_applicability/) | Give `ConfigurationTemplate` the same `applicability_mode` + `template_asset_class` / `template_model` allow-lists. **Reuse** the shared policy. Refactor the assignment guard off its hard-coded single-model match. Add the **guard-early** "can this modification even join this template" checkpoint. |

## Why this order

1. **Phase 1 builds the shared seam on the simpler case.** A modification → an asset is
   a one-hop check. Building `ApplicabilityPolicy` (the pure decision) and
   `ApplicabilitySyncHandler` (auto-derive the class set from the model set) here means
   Phase 2 inherits a proven, tested core.
2. **Phase 2 reuses that core and adds the only genuinely new logic** — the
   cross-entity, fail-early compatibility checkpoint that blocks an incompatible
   modification from being added to a template, plus the relaxation of the existing
   exact-model assignment gate ([D7](decisions.md)).

## How to use a phase sub-kit

1. Read the phase `README.md` for goal + exit criteria.
2. Read `business_concept.md` (what it delivers), then `data_relational_plan.md`
   (tables touched), then `control_layer_plan.md` (Structs / Managers / Policies /
   Validators / Handlers named per
   [`OOP_CONTROL_PATTERNS`](../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md)).
3. Keep the matrix doc open — every control-layer decision traces back to it.
4. After any schema change, **full DB rebuild** (`/db-rebuild`) — never incremental
   migrations (project rule).
