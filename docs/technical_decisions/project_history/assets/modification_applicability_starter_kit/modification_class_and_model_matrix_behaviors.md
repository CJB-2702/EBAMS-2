---
type: "Technical Decision"
title: "Modification Class & Model Matrix Behaviors"
description: "This is the **semantic heart** of the kit."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit]
context_tier: 2
---

# Modification Class & Model Matrix Behaviors

This is the **semantic heart** of the kit. It defines exactly how a modification's (or
template's) asset-class allow-list and asset-model allow-list combine to permit or refuse
application to a real asset. Everything in the control-layer plans implements this
document.

The same matrix governs **both** `DefinedModification` and `ConfigurationTemplate` — read
"the item" below as either.

---

## 1. The two lists and the mode

Every item carries:

- an **asset-class allow-list** — zero or more `AssetClass` rows,
- an **asset-model allow-list** — zero or more `AssetModel` rows,
- an **`applicability_mode`** — one of four values that decides how the lists are used.

The mode replaces the originally-requested pair of booleans
(`enforce_asset_class_match`, `enforce_models_match`). The mapping:

| `applicability_mode` | class enforced? | model enforced? |
| :--- | :---: | :---: |
| `STRICT` | ✅ | ✅ |
| `CLASS_ONLY` | ✅ | — |
| `MODEL_SET` | — | ✅ |
| `UNRESTRICTED` | — | — |

A list that is **not enforced** in the current mode is not discarded — it is retained as a
**suggestion / search hint** (e.g. "models people usually pick for this mod"). Only its
*binding* role changes.

---

## 2. The combine rule is AND

When both checks are enforced (`STRICT`), the asset must satisfy **both**:

```
allowed(asset) :=
    (NOT class_enforced  OR  asset.asset_class ∈ class_allow_list)
  AND
    (NOT model_enforced  OR  asset.model       ∈ model_allow_list)
```

Procedurally (this is the chained-rejection the user described):

1. If class is enforced and `asset.asset_class` is **not** in the class list → **reject**.
2. If model is enforced and `asset.model` is **not** in the model list → **reject**.
3. Otherwise → **allow**.

> **Why AND, not OR.** A model implies its one parent class, so the model list is the
> finer instrument. The "union" intuition ("Light Vehicles *plus* three specific trucks")
> is expressed by **choosing the right mode**, not by ORing two lists inside one config.
> See [D1](decisions.md#d1--combine-rule-is-and-or-considered-and-rejected).

---

## 3. The four modes, precisely

### `STRICT` — class AND model

Asset is allowed iff `asset.asset_class ∈ class_list` **and** `asset.model ∈ model_list`.

- Both lists are author-maintained and independent.
- **Dead-model guard ([D4](decisions.md#d4--dead-model-guard-in-strict-mode)):** a model
  whose parent class is not in the class list can never pass the AND. Adding such a model
  is **rejected** at author time.
- Coherent use — **intersection**: the model list spans several classes and the class
  list trims which of them actually qualify.

### `CLASS_ONLY` — class is the gate, models are hints

Asset is allowed iff `asset.asset_class ∈ class_list`. Any model in those classes
qualifies. The model list is **non-binding** — it surfaces as suggested/most-common models
for search and UX, nothing more.

### `MODEL_SET` — model is the gate, class set is derived

Asset is allowed iff `asset.model ∈ model_list`. The class list is **not authored** — it
is **system-maintained** to equal the distinct parent classes of the listed models
([D3](decisions.md#d3--class-set-is-auto-derived-in-model_set-mode-system-owned)). It
exists purely so class-level search/filter still works; it never narrows the gate (a
model in the list always passes, because its parent is, by construction, in the derived
class set).

> This is the "three closely-related heavy-duty trucks, but not all trucks" case.

### `UNRESTRICTED` — applies anywhere

Asset is always allowed. Both lists are pure **suggestions** to make searching easier; the
item may be applied to anything.

---

## 4. Summary table

| Mode | Allowed when… | Class list role | Model list role |
| :--- | :--- | :--- | :--- |
| `STRICT` | class ∈ classes **AND** model ∈ models | binding | binding (+ dead-model guard) |
| `CLASS_ONLY` | class ∈ classes | binding | suggestion / search |
| `MODEL_SET` | model ∈ models | **derived** (= parents of models) | binding |
| `UNRESTRICTED` | always | suggestion / search | suggestion / search |

---

## 5. Worked examples

Assume classes `LightVehicle`, `Truck`, `Laptop`; models `F150`, `Silverado`, `RamHD`
(all class `Truck`), `Corolla` (class `LightVehicle`), `ThinkPad` (class `Laptop`).

| Item config | Asset | Result | Why |
| :--- | :--- | :--- | :--- |
| Lift kit — `CLASS_ONLY`, classes `{Truck}` | a `Silverado` | ✅ | class `Truck` ∈ list |
| Lift kit — `CLASS_ONLY`, classes `{Truck}` | a `Corolla` | ❌ | class `LightVehicle` ∉ list |
| HD-only mod — `MODEL_SET`, models `{F150, Silverado, RamHD}` | a `RamHD` | ✅ | model ∈ list |
| HD-only mod — `MODEL_SET`, models `{F150, Silverado, RamHD}` | an `F250` (Truck, not listed) | ❌ | model ∉ list, even though class `Truck` matches the *derived* class set |
| Engine mod — `MODEL_SET`, models `{F150}` | a `ThinkPad` | ❌ | "engine mod on a laptop" — the headline case |
| Tint — `UNRESTRICTED` | anything | ✅ | applies anywhere |
| Intersection — `STRICT`, classes `{Truck}`, models `{F150, ThinkPad}` | adding `ThinkPad` | ⛔ **rejected at author time** | `ThinkPad`'s parent `Laptop` ∉ class list → dead model (D4) |

---

## 6. Defaults ([D7](decisions.md#d7--configurationtemplatemodel-retained-assignment-gate-generalized))

- **`DefinedModification`** defaults to `UNRESTRICTED` — preserves today's "apply
  anywhere" behavior until an author restricts it.
- **`ConfigurationTemplate`** defaults to `MODEL_SET` seeded with its own `model` FK —
  reproduces today's "assignable only to its authored model" gate until an author widens
  it.

---

## 7. Template–modification compatibility {#template-modification-compatibility}

A `ConfigurationTemplate` is a group of modifications. When a template is applied to an
asset, each of its modifications is in turn applied to that asset. So a modification is
**compatible** with a template only if every asset the template permits is also permitted
by the modification — i.e. the template's permitted asset-set ⊆ the modification's
permitted asset-set.

The earliest guard (checkpoint 2,
[`guard_and_checkpoint_map.md`](guard_and_checkpoint_map.md)) blocks an add **only when
the conflict is provable**; otherwise it allows and lets the runtime gate (checkpoint 3)
be the backstop ([D10](decisions.md#d10--templatemodification-compatibility-block-only-provable-conflicts)).

Let the **outer** set be the modification's permitted assets and the **inner** set be the
template's. Decidable common cases:

| Modification (outer) | Template (inner) | Verdict |
| :--- | :--- | :--- |
| `UNRESTRICTED` | anything | ✅ compatible (mod allows everything) |
| restricted (any) | `UNRESTRICTED` | ❌ **reject** — template applies anywhere, mod does not |
| `CLASS_ONLY` `C_out` | `CLASS_ONLY` `C_in` | ✅ iff `C_in ⊆ C_out`, else ❌ |
| `CLASS_ONLY` `C_out` | `MODEL_SET` `M_in` | ✅ iff every `m ∈ M_in` has `m.class ∈ C_out`, else ❌ |
| `MODEL_SET` `M_out` | `MODEL_SET` `M_in` | ✅ iff `M_in ⊆ M_out`, else ❌ |
| `MODEL_SET` `M_out` | `CLASS_ONLY` `C_in` | ❌ **reject** — a class permits models outside any finite `M_out` (unless the class's entire model set ⊆ `M_out`; treat as reject for safety) |
| `STRICT` `(C_out, M_out)` | `MODEL_SET` `M_in` | ✅ iff every `m ∈ M_in` is in `M_out` **and** `m.class ∈ C_out` |
| `STRICT` outer | `CLASS_ONLY`/`UNRESTRICTED` inner | ❌ reject (inner permits assets outside the strict intersection) |

General principle: **reject iff the template provably permits at least one (class, model)
the modification forbids; otherwise allow.** Implemented by
`ApplicabilityCompatibilityPolicy` (Phase 2). The runtime
`ModificationApplicabilityValidator` is the final guarantee regardless of what the
compatibility guard let through.
