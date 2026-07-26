---
type: "Technical Decision"
title: "Phase 1 — Control Layer Plan"
description: "Builds the **shared applicability engine** and wires the runtime gate (Checkpoint 3) into."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit, phase-1-modification-applicability]
context_tier: 2
---

# Phase 1 — Control Layer Plan

Builds the **shared applicability engine** and wires the runtime gate (Checkpoint 3) into
the existing `ModificationManager`. Everything implements
[`../modification_class_and_model_matrix_behaviors.md`](../modification_class_and_model_matrix_behaviors.md).

Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../harness/Architecture/OOP_CONTROL_PATTERNS.md).

---

## Shared components (built here, reused in Phase 2)

Home: `app/assets/control_layer/configurations/applicability/`.

### `ApplicabilityStruct` — read model

Aggregated, immutable view of one item's applicability. Built from either a
`DefinedModification` (this phase) or a `ConfigurationTemplate` (Phase 2) — it takes the
mode + the two id-sets, not the owning row, so it is entity-agnostic.

```
ApplicabilityStruct(
    mode: ApplicabilityMode,
    class_ids: frozenset[int],
    model_ids: frozenset[int],
)
  .binding_class_ids  -> frozenset[int]   # classes that actually gate, per mode
  .binding_model_ids  -> frozenset[int]   # models that actually gate, per mode
  .suggested_class_ids / .suggested_model_ids   # non-binding lists (search hints)
  .to_dict()
```

### `ApplicabilityPolicy` — the pure decision (the heart)

DB-free. Given an applicability and an asset's (class_id, model_id), returns allow/deny.
This is the single source of truth for the matrix; both runtime gates call it.

```
ApplicabilityPolicy.is_allowed(
    applicability: ApplicabilityStruct, *, asset_class_id: int, asset_model_id: int
) -> bool
```

Logic (matrix §2–§3):
- `UNRESTRICTED` → `True`.
- `CLASS_ONLY` → `asset_class_id in applicability.class_ids`.
- `MODEL_SET` → `asset_model_id in applicability.model_ids`.
- `STRICT` → `asset_class_id in class_ids AND asset_model_id in model_ids`.

A sibling `explain(...) -> str | None` returns the human reason for a denial (used by the
Validators to build their `ValueError` message) — keeps wording in one place.

### `ApplicabilitySyncHandler` — derive the class set (D3)

Single-task specialist. In `MODEL_SET` mode, recomputes an item's class allow-list to the
distinct parent classes of its model allow-list.

```
ApplicabilitySyncHandler(actor).sync_class_set(
    *, model_ids: Iterable[int]
) -> set[int]      # returns the derived class id set
```

The owning Manager (modification or template) is responsible for persisting the returned
set into its concrete junction table; the handler computes, it does not write entity-
specific rows. (It reads `AssetModel.objects.filter(id__in=...).values_list("asset_class_id")`.)

---

## `ModificationApplicabilityManager` — author the lists (Checkpoint 1)

Home: `applicability/modification_applicability_manager.py`. Sub-domain generalist over a
single `DefinedModification`'s applicability.

```
ModificationApplicabilityManager(actor)
  .set_mode(defined_mod, mode)            # normalizes lists on transition (see below)
  .add_class(defined_mod, asset_class)    # rejected if mode == MODEL_SET (derived) 
  .remove_class(defined_mod, asset_class)
  .add_model(defined_mod, model)          # STRICT: dead-model guard (D4)
  .remove_model(defined_mod, model)       # MODEL_SET: triggers class re-derive
  .struct(defined_mod) -> ApplicabilityStruct
```

**Integrity rules (Checkpoint 1):**

- `add_model` in `STRICT` mode → if `model.asset_class_id` not in the modification's class
  list, raise `ValueError` (dead-model guard, D4).
- `add_model` / `remove_model` in `MODEL_SET` mode → after the change, call
  `ApplicabilitySyncHandler.sync_class_set(...)` and rewrite `ModificationAssetClass` rows
  to the derived set.
- `add_class` / `remove_class` in `MODEL_SET` mode → **rejected** (class set is system-
  owned).
- `set_mode` transitions: entering `MODEL_SET` re-derives the class set; entering `STRICT`
  re-validates each existing model against the class set and reports any dead models;
  entering `CLASS_ONLY`/`UNRESTRICTED` leaves rows intact as suggestions.

All writes stamp `created_by` / `updated_by` from `actor` and run in `transaction.atomic()`
where multiple rows change (mode transitions, model-set sync).

---

## `ModificationApplicabilityValidator` — the runtime gate (Checkpoint 3)

Home: `app/assets/control_layer/guards/modification_applicability_guard.py` (alongside the
existing `configuration_assignment_guard.py`; class suffix `Validator` matches house
style).

```
ModificationApplicabilityValidator.check(asset, defined_modification) -> None
    # builds ApplicabilityStruct from the modification's mode + allow-lists
    # if not ApplicabilityPolicy.is_allowed(...): raise ValueError(explain(...))
```

Loads the modification's `mode`, `modification_asset_class` ids, and `modification_model`
ids; delegates the decision to `ApplicabilityPolicy`. Raises a descriptive `ValueError`
on denial (e.g. *"Modification 'Engine Swap' is restricted to models {…}; asset #42 uses
model 'ThinkPad X1' — not permitted."*).

---

## Wiring into the existing seam

`ModificationManager.add_actual_modification(asset, defined_modification, …)` —
**add one line** at the top, before the event/record transaction:

```python
ModificationApplicabilityValidator.check(asset, defined_modification)
with transaction.atomic():
    ...  # unchanged: creation_event, AssetEvent, ActualModification.create
```

No other change to `ModificationManager`. A denial raises before any event or row is
created, so a refused application leaves zero side effects.

---

## Delegation flow (record a modification on an asset — gated)

```
ModificationManager.add_actual_modification(asset, defined_modification)
  → ModificationApplicabilityValidator.check(asset, defined_modification)   # Checkpoint 3
       → ApplicabilityStruct(mode, class_ids, model_ids)
       → ApplicabilityPolicy.is_allowed(struct, asset_class_id, asset_model_id)
            False → raise ValueError(explain(...))     # nothing written
            True  ↓
  → transaction.atomic():
       Event + AssetEvent + ActualModification          # unchanged existing logic
```

## Delegation flow (author a modification's fit — MODEL_SET)

```
ModificationApplicabilityManager.add_model(defined_mod, model)
  (mode == MODEL_SET)
  → create ModificationModel row
  → ApplicabilitySyncHandler.sync_class_set(model_ids=<new full set>)
       → {m.asset_class_id for m in AssetModel.objects.filter(id__in=...)}
  → rewrite ModificationAssetClass rows to the derived class id set   # Checkpoint 1
```

## Verification hooks

- Unit-test `ApplicabilityPolicy.is_allowed` against every worked example in the matrix
  doc (§5) — table-driven.
- `add_actual_modification` raises for an engine-mod-on-laptop; succeeds for a permitted
  asset; succeeds unconditionally when the mod is `UNRESTRICTED`.
- In `MODEL_SET`, after adding/removing a model, `ModificationAssetClass` rows equal the
  distinct parents of the current `ModificationModel` set.
- In `STRICT`, adding a model whose parent class is absent from the class list raises.
- `grep` confirms the `ApplicabilityPolicy` import is the only place the matrix logic
  lives (no duplicated mode branching in the manager or validator).
