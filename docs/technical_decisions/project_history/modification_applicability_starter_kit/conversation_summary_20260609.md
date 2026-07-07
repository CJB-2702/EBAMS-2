# Conversation Summary — 2026-06-09

A chronological record of the Kit Builder session that produced this kit. Complements
[`brainstorming_session_20260608.md`](brainstorming_session_20260608.md) (the structured
narrative) with the actual back-and-forth and how the design converged.

## What the user asked for

Associate a **modification** with a set of allowable asset **classes** and/or **models**,
so an engine modification can't be put on a laptop. New tables (`modification_asset_class`,
`modification_model`) and enforce toggles on `DefinedModification`. Do the same for
`ConfigurationTemplate` (`template_asset_class`, `template_model`). Invoked via
`/kit-builder`, scope limited to **models + control layer** — no UI this pass.

## How the design converged

1. **Grounding.** Read the existing `assets` models and configuration control layer to
   find the real seams: `ModificationManager.add_actual_modification`,
   `ConfigurationManager.assign` → `ConfigurationAssignmentValidator` (which already
   hard-codes exact-model match), and `TemplateModificationManager.add_modification`.
   Confirmed `DefinedModification` had no class/model link (net-new) and
   `ConfigurationTemplate` already binds one `model`.

2. **Goal locked.** The user clarified the intent: modifications carry their own "where it
   belongs" rules at two granularities — broad (asset class) and narrow (a few specific
   models, "three closely-related heavy trucks but not all trucks"). Templates (groups of
   modifications) carry the same kind of rule.

3. **The OR → AND reversal.** The combine rule was first read as **OR**; the user's own
   four-row truth table corrected it to **AND**. Caught before any document was written.
   (→ [D1](decisions.md))

4. **Booleans → enum.** The four toggle combinations were named and modeled as a single
   `applicability_mode` enum: `STRICT`, `CLASS_ONLY`, `MODEL_SET`, `UNRESTRICTED`. The user
   chose the enum and asked for a dedicated matrix document. (→ [D2](decisions.md),
   [`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md))

5. **Derived class set + dead-model guard.** Because every `AssetModel` has exactly one
   parent `AssetClass`, the class list is derivable from the model list — so in
   `MODEL_SET` mode the class set is **auto-derived** (system-owned), and in `STRICT` mode
   a model whose parent class isn't listed is **rejected** as unreachable. (→ [D3](decisions.md),
   [D4](decisions.md))

6. **Guard as early as possible.** The user asked for a standalone document mapping the
   guards, relationships, and checkpoints across the whole lifecycle — produced as
   [`guard_and_checkpoint_map.md`](guard_and_checkpoint_map.md) (four checkpoints,
   earliest-first, with runtime backstops). (→ [D6](decisions.md))

## Decisions the assistant made on the user's behalf (flagged for review)

- **[D7](decisions.md)** — kept `ConfigurationTemplate.model` as the authored anchor and
  generalized the assignment gate; templates default to `MODEL_SET` + own-model so current
  behavior is preserved until deliberately widened.
- **[D3](decisions.md)** — chose **auto-derive** over validate-and-reject for the
  `MODEL_SET` class set (recommended; not explicitly chosen by the user).
- **[D10](decisions.md)** — the early add-to-template guard blocks only **provable**
  conflicts; indeterminate cases pass and rely on the runtime gate as backstop.

## Output

A two-phase kit (modifications first to build the shared engine, templates second to reuse
it + add the early compatibility guard) plus six root documents. See
[`README.md`](README.md) for the full index.

## Where it stands

Planning complete; no implementation started. Next step would be Phase 1
([`phase_1_modification_applicability/README.md`](phase_1_modification_applicability/README.md)).
