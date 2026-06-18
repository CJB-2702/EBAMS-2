# Decisions — Modification Applicability Kit

Architectural decision log. Each decision has a short ID, the options considered, and
what was chosen and why.

---

## D1 — Combine rule is **AND** (OR considered and rejected)

**Status:** Accepted

When **both** the class check and the model check are enforced, an asset is allowed only
if its class is in the class allow-list **AND** its model is in the model allow-list.

**Options considered:**
- **OR** — allowed if class matches *or* model matches. Briefly adopted because the
  phrasing "any Light Vehicle **plus** these three truck models" reads like a union.
- **AND** — allowed only if both match. **Chosen.**

**Why AND.** The user's own cleaned-up truth table resolves every combination as a
chained set of must-pass checks: "must have a matching asset class, then it must also
have a matching model." OR makes a `STRICT` config unable to express "restrict to these
specific models, which all live in these classes." The union use-case (different
classes permitted by different mechanisms) is instead expressed by choosing the
appropriate **mode** (`CLASS_ONLY` vs `MODEL_SET`), not by ORing within one config.
Full reasoning and worked examples:
[`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md).

---

## D2 — One `applicability_mode` enum, not two booleans

**Status:** Accepted

The request named two booleans (`enforce_asset_class_match`, `enforce_models_match`).
Their four combinations are four distinct, named behaviors, so they are modeled as a
single `ApplicabilityMode` enum field instead:

| Mode | (class enforced, model enforced) | Meaning |
| :--- | :--- | :--- |
| `STRICT` | (yes, yes) | Asset class **and** model must both match. |
| `CLASS_ONLY` | (yes, no) | Asset class must match; model list is a suggestion/search hint. |
| `MODEL_SET` | (no, yes) | Asset model must match a listed model; class list is **derived**. |
| `UNRESTRICTED` | (no, no) | Applies anywhere; both lists are suggestions/search hints. |

**Why.** An enum makes the illegal "half-configured" states unrepresentable, reads
clearly in the control layer (`if mode is STRICT:`), and gives the four behaviors first-
class names that the matrix doc and guards can reference. The user approved switching to
the enum.

---

## D3 — Class set is auto-derived in `MODEL_SET` mode (system-owned)

**Status:** Accepted

Every `AssetModel` has exactly one mandatory `asset_class` FK, so a model implies its
parent class. In `MODEL_SET` mode the class allow-list carries no independent
information — it is exactly the distinct parents of the listed models.

**Options considered:**
- **Validate-and-reject** — the user may type classes; the system rejects any that are
  not a parent of a listed model.
- **Auto-derive** — the system **maintains** the class rows; the user never edits them
  directly in this mode. **Chosen.**

**Why auto-derive.** Less to get wrong, no drift between the two lists, and the class
rows remain available for display/search filtering. Implemented by
`ApplicabilitySyncHandler` (see [D5](#d5--one-shared-decision-engine-concrete-tables-per-entity)),
which recomputes the class rows whenever the model set changes in `MODEL_SET` mode.

---

## D4 — Dead-model guard in `STRICT` mode

**Status:** Accepted

In `STRICT` mode both lists are independently authored and combined with AND. A listed
model whose parent class is **not** in the class allow-list can never satisfy the AND —
it is a *dead* (unreachable) entry and almost always a mistake.

**Decision:** adding such a model is **rejected** at author time with a clear message,
turning a silent footgun into an error. The one coherent `STRICT` use — *intersection*,
where the model set spans several classes and the class set trims it — is still fully
expressible (only genuinely unreachable models are blocked).

---

## D5 — One shared decision engine, concrete tables per entity

**Status:** Accepted

The match decision and the class-sync logic are **identical** for modifications and
templates, so they are built once and reused:

- `ApplicabilityPolicy` — a pure, DB-free decision: given a mode, an allowed-class set,
  an allowed-model set, and an asset's (class, model), return allow/deny. Built in
  Phase 1, reused unchanged in Phase 2.
- `ApplicabilitySyncHandler` — recomputes the derived class set from the model set in
  `MODEL_SET` mode. Shared.

The **junction tables stay concrete per entity** (`modification_asset_class`,
`template_asset_class`, …) — no abstract M2M base — matching the existing
`asset_class_capability` / `asset_model_domain` style. Only the *control-layer logic* is
shared, which is where the project already concentrates reuse.

**Physical home:** `app/assets/control_layer/configurations/applicability/`
(`applicability_policy.py`, `applicability_sync_handler.py`). Boundary guards live in the
existing `app/assets/control_layer/guards/` directory and are named `*Validator`.

---

## D6 — Guard as early as possible; four checkpoints, one map

**Status:** Accepted

Enforcement is not a single runtime gate; it is a chain. Earliest wins, with later gates
as backstops. The full map is
[`guard_and_checkpoint_map.md`](guard_and_checkpoint_map.md):

| # | Checkpoint | Guard | When |
| :--- | :--- | :--- | :--- |
| 1 | Edit a config's allow-lists | `ApplicabilitySyncHandler` + add-model integrity (D3/D4) | author time |
| 2 | Add a modification to a template | `TemplateModificationCompatibilityValidator` (fail-early) | author time |
| 3 | Apply a modification to an asset | `ModificationApplicabilityValidator` | runtime |
| 4 | Assign a template to an asset | `ConfigurationAssignmentValidator` (refactored, D7) | runtime |

---

## D7 — `ConfigurationTemplate.model` retained; assignment gate generalized

**Status:** Accepted (default approved — flag at implementation if undesired)

`ConfigurationTemplate` already has a single `model` FK and the existing
`ConfigurationAssignmentValidator` enforces `template.model_id == asset.model_id`
(exact single-model match). This kit generalizes that gate into the applicability-mode
system.

- The single `model` FK is **kept** — it remains the template's *authored-for* model and
  the anchor used by `create_new_revision()` and the `TemplateChild` self-reference
  guard. It is **not** the assignment gate anymore.
- The assignment gate moves into `ConfigurationAssignmentValidator` delegating to
  `ApplicabilityPolicy`.
- **Default to preserve today's behavior:** a new template defaults to
  `applicability_mode = MODEL_SET` with its own `model` auto-included in
  `template_model`. That reproduces the current "assignable only to its exact model"
  gate until an author widens it.
- `DefinedModification` has no pre-existing model link, so it defaults to
  `UNRESTRICTED` (today a modification can be applied anywhere; this default preserves
  that until an author restricts it).

> **Behavior-change flag:** widening a template to `CLASS_ONLY`/`UNRESTRICTED` relaxes
> the old hard exact-model match. That is the intended new capability; called out here so
> it is a conscious choice, not a regression.

---

## D8 — Table names normalized to the singular house convention

**Status:** Accepted

The request used plural names (`modification_asset_classes`, `template_models`). Existing
junctions are singular (`asset_class_capability`, `asset_model_domain`,
`template_modification`). The kit uses singular to match:

| Requested | Kit `db_table` |
| :--- | :--- |
| `modification_asset_classes` | `modification_asset_class` |
| `modification_models` | `modification_model` |
| `template_asset_classes` | `template_asset_class` |
| `template_models` | `template_model` |

---

## D9 — Scope: models + control layer only

**Status:** Accepted

Each phase delivers `business_concept.md`, `data_relational_plan.md`,
`control_layer_plan.md`. No `ui_features_plan.md`. The screens the user mentioned
("new tables and screens") are real future work but are **out of scope** here; the
control layer is designed so a thin UI can later drive it without reshaping.

---

## D10 — Template↔modification compatibility: block only *provable* conflicts

**Status:** Accepted

The earliest guard (checkpoint 2) blocks adding a modification to a template when the
template would **provably** permit an asset the modification forbids (e.g. an engine mod
into an any-laptop template). When compatibility is *indeterminate*, the add is
**allowed** and the runtime apply-mod gate (checkpoint 3) remains the backstop.

**Why fail-closed only on provable conflict.** A stricter "reject unless provably
compatible" would block legitimate authoring whenever set-algebra is ambiguous. Blocking
only the provable cases catches the obvious mistakes early without obstructing valid
work; the runtime gate guarantees correctness regardless. The decidable cases and the
subset semantics are tabulated in
[`modification_class_and_model_matrix_behaviors.md`](modification_class_and_model_matrix_behaviors.md#template-modification-compatibility).
