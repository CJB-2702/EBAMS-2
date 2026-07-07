# Guard & Checkpoint Map

The user's directive: **guard as early as possible.** Applicability is therefore enforced
as a *chain* of checkpoints, not a single runtime gate. Each row below is a point in the
lifecycle where the rules can be violated, the guard that fires there, and what it does.
Earlier guards catch mistakes at author time; later guards are the runtime guarantee.

This map spans both phases. Guards introduced in Phase 1 (modifications) are reused and
mirrored in Phase 2 (templates).

---

## The lifecycle chain

```
            ┌──────────────────────────────────────────────────────────────────┐
            │  AUTHOR TIME                                  RUNTIME             │
            └──────────────────────────────────────────────────────────────────┘

  define a               build a config's           add a mod                apply mod
  modification    ──►     allow-lists        ──►     to a template    ──►     to an asset
  / template              (classes, models)          (TemplateModification)   (ActualModification)
                              │                          │                        │
                          CHECKPOINT 1               CHECKPOINT 2             CHECKPOINT 3
                       sync + integrity         compatibility (early)       applicability gate
                                                                                 │
                                                       assign template      CHECKPOINT 4
                                                       to an asset    ──►   applicability gate
                                                       (AssetConfiguration)
```

---

## Checkpoint 1 — Editing a config's allow-lists (author time)

**Where:** `ModificationApplicabilityManager` (P1) / `TemplateApplicabilityManager` (P2)
— the `set_mode`, `add_class`, `add_model`, `remove_*` operations.

**Guards:**

- **`ApplicabilitySyncHandler` (shared).** In `MODEL_SET` mode, after any change to the
  model list, recompute the class rows to equal the distinct parent classes of the listed
  models ([D3](decisions.md)). The user cannot hand-edit classes in this mode.
- **Dead-model integrity (D4).** In `STRICT` mode, reject adding a model whose parent
  class is not in the class allow-list (unreachable entry).
- **Mode-transition normalization.** When switching modes, reconcile the lists:
  entering `MODEL_SET` triggers a class re-derive; entering `STRICT` re-validates existing
  models against the class list (surface dead models); entering `CLASS_ONLY`/`UNRESTRICTED`
  demotes the now-non-binding list to "suggestion" without deleting it.

**Failure mode prevented:** a config that is internally inconsistent (class/model lists
that contradict the mode) ever reaching the database.

---

## Checkpoint 2 — Adding a modification to a template (author time, **earliest cross-entity guard**)

**Where:** `TemplateModificationManager.add_modification()` (P2).

**Guard:** `TemplateModificationCompatibilityValidator` → `ApplicabilityCompatibilityPolicy`.

Blocks the add **only when the conflict is provable** — i.e. the template would permit at
least one asset (class/model) the modification forbids
([D10](decisions.md), subset rules in
[`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md#template-modification-compatibility)).
When compatibility is indeterminate, the add is allowed and Checkpoint 3 is the backstop.

**Failure mode prevented (early):** grouping an "engine mod" (restricted to specific
truck models) into an "any-laptop" template — caught at the moment of authoring the
template, long before anyone tries to apply it.

---

## Checkpoint 3 — Applying a modification to an asset (runtime gate)

**Where:** `ModificationManager.add_actual_modification()` (P1) — *currently has no such
check*.

**Guard:** `ModificationApplicabilityValidator.check(asset, defined_modification)` →
`ApplicabilityPolicy.is_allowed(...)`. Raises `ValueError` if the asset's (class, model)
is not permitted by the modification's mode + allow-lists.

**Failure mode prevented:** the headline case — an engine modification physically being
recorded against a laptop asset. This is the **final guarantee** for modifications: even
if a mod slipped into a template (Checkpoint 2 indeterminate), this gate refuses the
actual application.

---

## Checkpoint 4 — Assigning a template to an asset (runtime gate)

**Where:** `ConfigurationManager.assign()` → `ConfigurationAssignmentValidator.check()`
(P2). Today this validator hard-codes `template.model_id == asset.model_id`; it is
**refactored** to delegate to `ApplicabilityPolicy` using the template's mode + allow-lists
([D7](decisions.md)).

**Guard:** `ConfigurationAssignmentValidator` → `ApplicabilityPolicy.is_allowed(...)`,
plus the retained `is_active` check.

**Failure mode prevented:** assigning a template to an asset outside the template's
permitted class/model set. With the default `MODEL_SET`+own-model seed, this reproduces
today's exact-model gate; widening the mode relaxes it deliberately.

---

## Backstop relationship

| If this is missed… | …this catches it |
| :--- | :--- |
| Checkpoint 1 (bad list authored via a raw path) | Checkpoints 3 & 4 still evaluate the live lists at apply/assign time |
| Checkpoint 2 (indeterminate compatibility allowed) | Checkpoint 3 refuses the actual modification on the offending asset |
| Checkpoint 2 (mod added before its restrictions tightened) | Checkpoint 3 refuses application to now-disallowed assets |

The chain is defense-in-depth: author-time guards give fast, friendly feedback; runtime
guards (3 & 4) are the invariant that cannot be bypassed.

---

## Shared vs per-phase

| Component | Built in | Reused in |
| :--- | :--- | :--- |
| `ApplicabilityPolicy` (pure decision) | Phase 1 | Phase 2 |
| `ApplicabilitySyncHandler` (derive class set) | Phase 1 | Phase 2 |
| `ModificationApplicabilityValidator` (Checkpoint 3) | Phase 1 | — |
| `ConfigurationAssignmentValidator` refactor (Checkpoint 4) | — | Phase 2 |
| `ApplicabilityCompatibilityPolicy` + `TemplateModificationCompatibilityValidator` (Checkpoint 2) | — | Phase 2 |
