# Phase 2 — Control Layer Plan

Reuses the Phase 1 engine for templates, generalizes the assignment gate, and adds the
earliest cross-entity guard. No matrix logic is re-implemented — `ApplicabilityPolicy`,
`ApplicabilityStruct`, and `ApplicabilitySyncHandler` are imported from Phase 1 unchanged.

Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md).

---

## Reused from Phase 1 (no changes)

- `ApplicabilityMode` (enum), `ApplicabilityStruct`, `ApplicabilityPolicy`,
  `ApplicabilitySyncHandler`.

Because `ApplicabilityStruct` is entity-agnostic (mode + two id-sets), templates build one
the same way modifications do.

---

## `TemplateApplicabilityManager` — author the lists (Checkpoint 1)

Home: `applicability/template_applicability_manager.py`. Mirrors
`ModificationApplicabilityManager` exactly, operating on a `ConfigurationTemplate` and its
`TemplateAssetClass` / `TemplateModel` rows.

```
TemplateApplicabilityManager(actor)
  .set_mode(template, mode)
  .add_class(template, asset_class)     # rejected if mode == MODEL_SET (derived)
  .remove_class(template, asset_class)
  .add_model(template, model)           # STRICT: dead-model guard (D4)
  .remove_model(template, model)        # MODEL_SET: triggers class re-derive
  .struct(template) -> ApplicabilityStruct
```

Same integrity rules as Phase 1 (sync via `ApplicabilitySyncHandler`, dead-model guard,
mode-transition normalization). The two managers are close enough that a shared private
mixin/base may be extracted during implementation — but the **tables stay distinct**
([D5](../decisions.md)); only behavior is shared.

### Default seeding (D7)

`ConfigurationTemplateManager.create(...)` (existing) is extended so a new template lands
with `applicability_mode = MODEL_SET` and a `TemplateModel` row for its own `model`. This
reproduces today's "assignable only to its model" gate from creation. Implement by calling
`TemplateApplicabilityManager.add_model(template, template.model)` inside the existing
`create()` transaction.

---

## `ApplicabilityCompatibilityPolicy` — subset decision (shared, new)

Home: `applicability/applicability_compatibility_policy.py`. Pure, DB-free. Decides
whether an **inner** applicability (the template's) is provably **not** a subset of an
**outer** applicability (the modification's) — i.e. whether the template provably permits
an asset the modification forbids.

```
ApplicabilityCompatibilityPolicy.provably_incompatible(
    *, inner: ApplicabilityStruct, outer: ApplicabilityStruct,
    class_models: Mapping[int, frozenset[int]] | None = None,
) -> str | None        # reason string if provably incompatible, else None
```

Implements the decidable cases in
[matrix §7](../modification_class_and_model_matrix_behaviors.md#template-modification-compatibility):
- `outer.mode == UNRESTRICTED` → never incompatible.
- restricted `outer` + `inner.mode == UNRESTRICTED` → incompatible.
- `CLASS_ONLY`/`MODEL_SET`/`STRICT` pairings → the subset tests tabulated in §7.
- Indeterminate → return `None` (allow; D10). `class_models` (class_id → its model_ids) is
  the optional lookup used where a class must be expanded to its models; when absent, those
  cases resolve to "allow" rather than guessing.

---

## `TemplateModificationCompatibilityValidator` — the early gate (Checkpoint 2)

Home: `guards/template_modification_compatibility_guard.py`.

```
TemplateModificationCompatibilityValidator.check(template, defined_modification) -> None
    inner = TemplateApplicabilityManager(...).struct(template)        # or build directly
    outer = <modification ApplicabilityStruct>
    reason = ApplicabilityCompatibilityPolicy.provably_incompatible(inner=inner, outer=outer)
    if reason: raise ValueError(reason)
```

Wired into `TemplateModificationManager.add_modification(...)` — **add one line** before
the existing duplicate-link check:

```python
TemplateModificationCompatibilityValidator.check(template, defined_modification)
if TemplateModification.objects.filter(...).exists():   # unchanged
    ...
```

---

## `ConfigurationAssignmentValidator` — refactor the runtime gate (Checkpoint 4)

Home: `guards/configuration_assignment_guard.py` (existing). **Replace** the hard-coded
`template.model_id == asset.model_id` branch with a delegation to `ApplicabilityPolicy`;
keep the `is_active` check.

```
ConfigurationAssignmentValidator.check(asset, template) -> None
    if not template.is_active: raise ValueError(...)               # kept
    struct = <template ApplicabilityStruct>
    if not ApplicabilityPolicy.is_allowed(struct, asset_class_id=asset.asset_class_id,
                                           asset_model_id=asset.model_id):
        raise ValueError(ApplicabilityPolicy.explain(...))
```

`ConfigurationManager.assign` already calls this validator — **no change** to the manager.
With the default `MODEL_SET`+own-model seed, behavior is identical to today; widening the
mode is what relaxes the gate.

> **Note:** `asset.asset_class_id` is reached via `asset.model.asset_class_id` if `Asset`
> has no direct class FK — confirm the access path at implementation; the policy only needs
> the two integer ids.

---

## Delegation flow (add a modification to a template — early guard)

```
TemplateModificationManager.add_modification(template, defined_modification)
  → TemplateModificationCompatibilityValidator.check(template, defined_modification)  # Checkpoint 2
       inner = ApplicabilityStruct(template…)
       outer = ApplicabilityStruct(modification…)
       → ApplicabilityCompatibilityPolicy.provably_incompatible(inner, outer)
            reason → raise ValueError(reason)      # blocked at author time
            None   ↓                               # indeterminate/compatible → allow
  → existing duplicate check + TemplateModification.create
```

## Delegation flow (assign a template to an asset — generalized gate)

```
ConfigurationManager.assign(asset, template)
  → ConfigurationAssignmentValidator.check(asset, template)            # Checkpoint 4
       → is_active check (kept)
       → ApplicabilityPolicy.is_allowed(template struct, asset ids)
            False → raise ValueError(explain(...))
            True  ↓
  → transaction.atomic(): AssetConfiguration + event   # unchanged existing logic
```

## Verification hooks

- Template and modification gates produce **identical** verdicts for identical
  (mode, lists, asset) inputs — proven by pointing both validators' tests at the same
  `ApplicabilityPolicy` cases.
- A freshly created template is `MODEL_SET` with its own model and assignable only to that
  model (today's behavior, by default).
- `add_modification` rejects an engine-mod (`MODEL_SET` over 3 trucks) into an
  `UNRESTRICTED` template; allows it into a `MODEL_SET` template whose models ⊆ the mod's.
- A modification allowed into a template under indeterminate compatibility is still refused
  by `add_actual_modification` on a disallowed asset (Checkpoint 3 backstop).
- `grep` confirms no second copy of the matrix logic — only `ApplicabilityPolicy` and
  `ApplicabilityCompatibilityPolicy` decide.
