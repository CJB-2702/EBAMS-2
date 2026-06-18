# Mock Data Shapes

The hard-coded fixtures that feed the applicability prototype. They **extend** the
existing assets-mock dicts in
[`app/assets/presentation_layer/mock_data.py`](../app/assets/presentation_layer/mock_data.py)
(`DEFINED_MODIFICATIONS`, `CONFIGURATION_TEMPLATES`) with the fields the real Phase-1
tables added — so the mock mirrors the true model shape. **No ORM, no control-layer call
in the prototype**; a pure helper reproduces the matrix verdict.

Field names match the real models:
[`applicability_mode`](../app/assets/models/configurations/defined_modification.py),
[`ModificationAssetClass`](../app/assets/models/configurations/modification_asset_class.py),
[`ModificationModel`](../app/assets/models/configurations/modification_model.py).

## Extended modification fixture

```python
# Existing rows gain: applicability_mode + applicable_classes + applicable_models.
# class/model ids reference the existing ASSET_CLASSES / ASSET_MODELS mock ids.
DEFINED_MODIFICATIONS = [
    {"id": 1, "name": "Side Shifter", "code": "SS01", "category": "Attachment",
     "description": "Hydraulic side shift carriage.", "is_active": True,
     "applicability_mode": "class_only",          # binding: classes; models = hints
     "applicable_classes": [1],                    # Forklift
     "applicable_models": [1]},                    # 8FGCU25 (suggestion only)

    {"id": 2, "name": "Cold Cab", "code": "CC01", "category": "Cab",
     "description": "Insulated heated operator cab.", "is_active": True,
     "applicability_mode": "model_set",            # binding: models; classes derived
     "applicable_classes": [1],                    # DERIVED from model 1's class
     "applicable_models": [1]},

    {"id": 3, "name": "LED Work Lights", "code": "LED1", "category": "Electrical",
     "description": "Front + rear LED light kit.", "is_active": True,
     "applicability_mode": "unrestricted",         # applies anywhere
     "applicable_classes": [],
     "applicable_models": []},

    {"id": 4, "name": "Engine Swap", "code": "ENG1", "category": "Powertrain",
     "description": "Heavy-duty engine replacement.", "is_active": True,
     "applicability_mode": "strict",               # binding: class AND model
     "applicable_classes": [2],                    # Excavator
     "applicable_models": [2]},                    # 320 GX  (parent class 2 — coherent)
]
```

> The four rows are chosen to exercise **all four modes** so every editor state and
> preview path is visible in the prototype. Row 4 + a Forklift asset is the headline
> *engine-mod-on-the-wrong-thing* ✗ case.

## Extended template fixture *(Phase 2)*

```python
CONFIGURATION_TEMPLATES = [
    {"id": 1, "name": "Cold Storage Forklift", "revision": "A", "model": 1,
     "is_active": True, "description": "Standard build for refrigerated warehouses.",
     "modifications": [1, 2, 3], "children": [...],
     "applicability_mode": "model_set",            # default for templates (kit D7)
     "applicable_classes": [1],                    # derived from model 1
     "applicable_models": [1]},                    # seeded from the template's own model
]
```

## The matrix mock helper (no ORM)

A pure function reproducing
[`ApplicabilityPolicy.is_allowed`](../app/assets/control_layer/configurations/applicability/applicability_policy.py)
for the preview + gated picker. **This is the only logic in the prototype** — and it is a
deliberate, faithful copy of the real policy so the two visibly agree (and so the wire-up
later is a drop-in replacement):

```python
def mock_is_allowed(mode, class_ids, model_ids, *, asset_class_id, asset_model_id):
    if mode in ("strict", "class_only") and asset_class_id not in class_ids:
        return False, f"class not in permitted set {sorted(class_ids) or '{}'}"
    if mode in ("strict", "model_set") and asset_model_id not in model_ids:
        return False, f"model not in permitted set {sorted(model_ids) or '{}'}"
    return True, None

def mock_derive_classes(model_ids):
    # mirrors ApplicabilitySyncHandler: distinct parent class of each model
    return sorted({m["asset_class"] for m in ASSET_MODELS if m["id"] in model_ids})
```

> Keeping the mock helper a line-for-line mirror of the real policy is intentional:
> when the assets app goes real, the editor/preview swap `mock_is_allowed` →
> `ApplicabilityPolicy.is_allowed` and `mock_derive_classes` →
> `ApplicabilitySyncHandler.sync_class_set` with no template change.

## Sample assets for the "Applies to" preview

A small fixed set (subset of the existing `ASSETS` mock) chosen to surface every verdict,
including a cross-class case:

```python
PREVIEW_ASSETS = [
    {"id": 1, "name": "FL-North-014", "asset_class": 1, "model": 1},  # Forklift / 8FGCU25
    {"id": 3, "name": "EX-Eng-002",   "asset_class": 2, "model": 2},  # Excavator / 320 GX
    # a Forklift on a non-listed model, to show MODEL_SET ✗ within an allowed class
    {"id": 9, "name": "FL-South-021", "asset_class": 1, "model": 9},
]
```

## Mode → tag colour map (list/card UI helper)

Reuses the existing `_status_tag.html` idiom.

| `applicability_mode` | Label | Bulma tag |
| :--- | :--- | :--- |
| `unrestricted` | Unrestricted | `is-light` |
| `class_only` | Class only | `is-info` |
| `model_set` | Model set | `is-link` |
| `strict` | Class + model | `is-warning` |

## What the prototype deliberately fakes

- **Persistence.** The editor POSTs to a dummy success and flashes a message; no row is
  written (matches every other assets-mock form).
- **Derivation.** `mock_derive_classes` recomputes on the client/server render, not via a
  DB trigger.
- **Compatibility (P2).** The template compatibility verdicts are precomputed in the mock
  for the sample data, not run through `ApplicabilityCompatibilityPolicy` (which doesn't
  exist until Phase 2 control is built).
