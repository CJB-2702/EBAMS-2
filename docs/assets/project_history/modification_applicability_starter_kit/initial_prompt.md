---
type: "Technical Decision"
title: "Initial Prompt — Modification Applicability Kit"
description: "These answers are binding for the kit (see [decisions.md](decisions.md) for the."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit]
context_tier: 2
---

# Initial Prompt — Modification Applicability Kit

## Originating request (verbatim intent)

> I want to be able to associate a modification with a set of allowable asset classes
> or [asset] models. This will require new tables and screens:
> - modification asset classes
> - modification models
> - and booleans on the defined modification: `enforce_asset_class_match`,
>   `enforce_models_match`.
>
> I want to do a similar thing with `ConfigurationTemplate`. Let's create template
> asset classes table and template models tables: `enforce_model_match`,
> `enforce_asset_class_match`.
>
> Let's brainstorm just the models and control layer for now.

> The goal is that for a defined modification I shouldn't be able to put an engine
> modification onto a laptop. Modifications have their own associations and rules about
> where they should be applied. I should be able to associate a modification generically
> with an asset class and enforce that it's not accidentally applied somewhere it
> shouldn't be.
>
> In the same thought process a template is a set of modifications. If I group together
> a wheel mod, a lift kit and a tint, I should be able to associate the template itself
> with the asset class.
>
> Sometimes an individual modification can be associated with a couple of closely
> related models (e.g. three very similar heavy-duty trucks) but not the entire set of
> trucks.

## Clarifying decisions captured during interrogation

These answers are binding for the kit (see [`decisions.md`](decisions.md) for the
reasoned versions, and
[`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md)
for the full truth table).

1. **Combine rule is AND, not OR.** An initial reading favored OR; the user's
   four-row truth table resolved it to **AND** (when both class and model are enforced,
   the asset must satisfy **both**). *(→ D1.)*

2. **Two booleans become one `applicability_mode` enum.** The four toggle combinations
   are four named modes — `STRICT`, `CLASS_ONLY`, `MODEL_SET`, `UNRESTRICTED` — modeled
   as a single enum so illegal/confusing states are unrepresentable. *(→ D2.)*

3. **The class set is auto-derived in `MODEL_SET` mode.** Because every `AssetModel` has
   exactly one mandatory parent `AssetClass`, when only the model set is enforced the
   class rows are **system-maintained** to equal the distinct parents of the listed
   models — the user never hand-keys them. *(→ D3.)*

4. **Dead-model guard in `STRICT` mode.** A model whose parent class is not in the class
   allow-list can never satisfy the AND, so adding such a model is **rejected** at
   author time rather than silently creating an unreachable entry. *(→ D4.)*

5. **One shared decision engine, concrete tables per entity.** The match logic
   (`ApplicabilityPolicy`) and the class-sync logic (`ApplicabilitySyncHandler`) are
   built once and reused by both modifications and templates. The junction tables stay
   concrete per entity (no abstract base), matching the existing `*_capability` /
   `*_domain` junction style. *(→ D5.)*

6. **Guard as early as possible, with a dedicated map.** Enforcement fires at three
   checkpoints — apply-mod-to-asset, assign-template-to-asset, and (earliest)
   add-mod-to-template — plus relational-integrity sync at allow-list edit time. The
   user requested a standalone document outlining the guards, relationships, and
   checkpoints throughout the process:
   [`guard_and_checkpoint_map.md`](guard_and_checkpoint_map.md). *(→ D6.)*

7. **Symmetry between modifications and templates.** The identical four-mode matrix
   applies to `ConfigurationTemplate`; the existing exact-single-model assignment gate
   is generalized into the mode system. *(→ D1, D7.)*

8. **Scope: models + control layer only.** Each phase produces `business_concept.md`,
   `data_relational_plan.md`, and `control_layer_plan.md`. **No** `ui_features_plan.md`
   — the screens the user mentioned are deferred and noted as out of scope. *(→ D9.)*
