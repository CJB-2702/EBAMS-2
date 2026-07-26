# Config Baseline Redesign — Implementation Plan

> Review document. No code has been changed. Approve before any work begins.

## 1. Context & Problem

`AssetModel` today carries a single `config_baseline` string (e.g. `LE`) that is **part of its
identity** — the natural key is `(model_name, config_baseline, version)`. This forces a **separate
model row for every trim/baseline**, even when the baseline changes nothing about maintenance,
dispatch, or capabilities.

Both current workarounds are poor:
- **Proliferate model rows** — near-duplicate `AssetModel`s (`Corolla LE 2016`, `Corolla EX 2016`, …).
- **Empty `ConfigurationTemplate`s** — too much user effort; nobody will do it.

**Goal.** One model row per `(model_name, version)`. The model holds an **allow-list of acceptable
baselines** (`Corolla 2016 → [LE, EX, SE]`). Each **Asset records the one baseline it actually is**
(`this forklift = LE`). The acceptable-value constraint is enforced **at the UI layer** (a dropdown),
**not** by the database or server — off-list values are still accepted (soft), so imports/API writes
never fail.

## 2. Decisions (locked)

| Decision | Choice |
| :-- | :-- |
| Per-asset baseline | New `Asset.config_baseline` string field |
| Allow-list storage | `AssetModel.config_baselines` — `JSONField` list of strings (portable across sqlite-dev / postgres-prod; `ArrayField` is not sqlite-safe; matches existing `Asset.tags`) |
| Enforcement | **UI constraint** (dropdown sourced from the model's list) — soft at DB/server, no hard rejection |
| Off-list values | Allowed; interactive users add them via an "➕ Add new baseline…" option that feeds back into the model's list |
| Natural key | Drops baseline → `(model_name, version)` |

## 3. Data Model Changes

**`app/assets/models/core/asset_model.py`**
- Replace `config_baseline = CharField(...)` with `config_baselines = models.JSONField(default=list, blank=True)`
  (callable default `list`, never a mutable literal).
- **Make `version` non-nullable**: `version = models.CharField(max_length=100, blank=True, default="")`
  (was `null=True`). A blank version is now `""`, not `NULL` — this is what lets the uniqueness
  constraint below be a single clean index across sqlite + postgres.
- Add a **`Meta.constraints`** unique constraint (see §4a).
- `Meta.ordering`: `["model_name", "config_baseline"]` → `["model_name", "version"]`.
- `__str__`: drop the baseline segment → `model_name — version` (a model now spans baselines).
  (`if self.version:` still short-circuits on `""`.)
- Refresh the docstring's identity note (baseline is now an accepted-value set, not a column value).

**`app/assets/models/core/asset.py`**
- Add `config_baseline = models.CharField(max_length=200, null=True, blank=True)`.
- **Comment on the field** documenting the constraint model: the acceptable-value constraint is
  **UI-only** — components MUST present this as a **dropdown** sourced from the owning
  `AssetModel.config_baselines`. DB/server do **not** hard-reject off-list values (soft by design),
  so ingestion/import/API paths never fail.

## 4a. Uniqueness Constraint (model + version)

Today uniqueness is **app-layer only** (`AssetModelUniquenessValidator`), with no DB constraint.
Add a hard DB backstop on `AssetModel`:

```python
class Meta:
    db_table = "asset_model"
    ordering = ["model_name", "version"]
    constraints = [
        models.UniqueConstraint(fields=["model_name", "version"], name="uq_assetmodel_identity"),
    ]
```

- Works identically on sqlite (dev) and postgres (prod) **because `version` is now non-null** (`""`
  for "no version"); no partial constraints or synthetic composite-key column needed.
- **Keep the app-layer validator** — the DB constraint is exact/case-sensitive (`Corolla` ≠ `corolla`);
  the validator still runs first for friendly, case-insensitive messages before the DB rejects.
- The validator drops `config_baseline` from its key (→ `model_name + version`) as already planned;
  its blank handling must compare `version or ""` (not `None`) to match the new column.
- **Seed collapse watch:** the constraint fails the migration/seed if two rows share
  `(model_name, version)`. That is the intended surfacing of duplicates — reconcile during rebuild.

## 4. Control Layer

**Uniqueness guard — `control_layer/guards/asset_model_uniqueness_guard.py`**
- Remove the `config_baseline` parameter and its `.filter(...)`; key becomes `(model_name, version)`.
- Update the duplicate-error message to name only `model_name + version`.

**Advisory guard (new) — `control_layer/guards/asset_config_baseline_guard.py`**
- The dropdown is the real constraint; this is a **light advisory** for non-UI paths (API/import/F5
  fallback). `AssetConfigBaselineValidator.check(*, value, model) -> list[str]` returns a warning
  (never raised) when `value` is non-blank and not in `model.config_baselines` (case-insensitive).
  Optional to surface — not a gate.

**AssetModel write path**
- `control_layer/adapters/asset_model_adaptor.py` — parse a comma-separated `config_baselines` POST
  field into a normalized list (trimmed, de-duped, non-empty); drop the old `config_baseline` key.
- `control_layer/asset_model_context.py` — in `_METADATA_FIELDS` swap `config_baseline` →
  `config_baselines` (it's a list; exclude from the blank→None coercion set). Add domain verb
  `add_config_baseline(self, value)` (append + case-insensitive dedup + save) to back the "add" flow.
- `control_layer/factories/asset_model_factory.py` — pass `config_baselines=data.get("config_baselines") or []`;
  update the uniqueness-validator call (no `config_baseline`).
- `control_layer/domain_structs/asset_model_struct.py` — `to_dict` key → `config_baselines`.

**Asset write path**
- `control_layer/adapters/asset_create_adaptor.py` — add `config_baseline` (trimmed, blank→None) and a
  boolean `add_baseline_to_model` (set by the dropdown's "Add new baseline…" path).
- `control_layer/factories/asset_factory.py` — set `config_baseline` on the new `Asset` (store whatever
  arrives — soft). If `add_baseline_to_model` and the value is new, append it to the model's list.
  Optionally run the advisory guard and return warnings.
- `control_layer/asset_context.py` — add `config_baseline` to the editable field set in `update()`;
  honor `add_baseline_to_model` via `AssetModelContext(a.model_id, actor).add_config_baseline(value)`.
- `presentation_layer/entrypoints/assets.py` (`asset_create`, `asset_edit`) — relay any advisory
  warnings via `messages.warning(...)`. One POST, no extra endpoint, F5-safe.

## 5. Presentation

- **`templates/assets/models/form.html`** — replace the single Config Baseline input with an
  **"Accepted Config Baselines"** comma-separated input (value = `config_baselines|join:", "`), helper
  text, existing info-popover pattern.
- **`templates/assets/models/detail.html`** — render `config_baselines` as tags; empty state `None.`
  (always-render-card rule).
- **`templates/assets/assets/form.html`** — *the UI constraint lives here*:
  - A **Config Baseline `<select>`** whose options come from the **selected model's** `config_baselines`.
    Each model `<option>` carries a `data-baselines` JSON attribute; small JS repopulates the baseline
    `<select>` on model change. F5-safe: on edit, the server renders the current model's options and
    pre-selects `asset.config_baseline`.
  - A trailing **"➕ Add new baseline…"** option that reveals a text input and sets `add_baseline_to_model`
    — the only interactive way to introduce an off-list value; it feeds back into the model's list.
  - Model `<option>` label drops `config_baseline`, keeps `version`.
- **`templates/assets/assets/detail.html`** — show `asset.config_baseline` in the Identity block
  (and optionally the subtitle).
- **`templates/assets/models/list.html`** — update the explanatory card: baseline is now a **set on the
  model**; the asset records which one. Keep the example table, reframed accordingly.

## 5a. Utility — Prefill "New Model" from an existing model

Convenience on the **create** page: pick an existing model and copy its fields into the form as a
starting point (common when adding a sibling variant). F5-safe, no new write path.

- **`presentation_layer/entrypoints/models.py` → `model_create` (GET):** read `?copy_from=<model_id>`;
  if present, load that `AssetModel` and pass it as the `model` context var (prefill) plus
  `selected_manufacturer_ids`. `mode` stays `"create"`, so POST still creates a **new** row — the source
  is only a template. Always pass `all_models` (ordered `model_name, version`) for the selector.
- **`templates/assets/models/form.html` (create mode only):** a "Prefill from existing model" `<select>`
  at the top; choosing an option navigates to `{% url 'model_create' %}?copy_from=<id>` (plain GET,
  full-page render with fields filled). Reuses the existing `value="{{ model.<field> }}"` bindings,
  including `config_baselines|join:", "` and `selected_manufacturer_ids`.
- No control-layer change; this is read + render only.

## 6. Search / Ordering

- `search/asset_model_search.py` — drop `config_baseline` from the `q` OR-filter (JSON `__icontains`
  isn't portable); search `model_name + version`; order by `("model_name", "version")`.
- `search/capability_search.py`, `search/configuration_search.py` — change every
  `order_by/values_list("model_name","config_baseline")` to `"version"` (can't order by a JSON list).
- `search/asset_search.py` (recommended) — add a `config_baseline` substring filter, include it in the
  asset `q`, and surface it as a column/filter on `assets/list.html`. Baseline is now an **asset-level**
  attribute, so filtering belongs here.

## 7. Seed Data

- `presentation_layer/mock_data.py` — `ASSET_MODELS`: `config_baseline` (string) → `config_baselines`
  (list; `null → []`, `"Cushion Tire" → ["Cushion Tire"]`); `_model_ns.display_name` drops the baseline
  segment (keep `version`). Add `config_baseline` to `ASSETS` rows.
- `app/assets/fixtures/dev_assets_base.json` — on `assets.assetmodel` rows convert `config_baseline` →
  `config_baselines` (wrap value in a list, `null → []`); add `config_baseline` to `assets.asset` rows
  (nullable). Leave `assets.configurationtemplate.revision` untouched.
- **Uniqueness watch** — dropping baseline from the key means two seed models sharing
  `(model_name, version)` now collide (`version` is nullable). Verify during rebuild; merge colliding
  pairs (that's the intended collapse) or differentiate by `version`.

## 8. Migration

Schema change (column drop/add + type change) → **full reset**, per the always-apply rule: fix the
fixture first, then `python dev_tools/delete_database_rebuild_models.py --seed`. No incremental migrations.

## 9. Verification

1. `python manage.py check` clean; full reset + seed completes without fixture errors.
2. New `0001_initial` shows `config_baselines` (JSON) on `asset_model` and `config_baseline` on `asset`;
   no `config_baseline` column on `asset_model`.
3. Control-layer round-trip (`manage.py shell`):
   - Create `AssetModel` "Corolla" / version "2016" / `config_baselines=["LE","EX"]`; assert
     `str(m) == "Corolla — 2016"`; a second "Corolla"/"2016" is now a **duplicate**.
   - Asset with `config_baseline="LE"` → stored, in-list. Asset with off-list `"LX"` +
     `add_baseline_to_model=True` → asset stores `"LX"` **and** `"LX"` appended to `m.config_baselines`.
     Confirm the server never rejects an off-list value.
4. Render (test `Client`, `force_login`, `ALLOWED_HOSTS=['*']`): `model_index`, `model_create/edit`,
   `model_detail`, `asset_create/edit`, `asset_detail` all 200; asset form's baseline `<select>` is
   populated from the chosen model's list and each model option carries `data-baselines`; model detail
   shows baseline tags; list card reflects allow-list semantics.
5. Remove any shell-created test rows afterward.

## 10. Out of Scope (noted, not built)

- Inheriting the allow-list from a base model to its revisions.
- Coupling the allow-list to `ConfigurationTemplate` selection — baseline stays a lightweight,
  UI-constrained label, deliberately decoupled from the build-spec machinery.

## Appendix — Rejected Alternatives (why B won)

- **A. Free text + sibling datalist** — zero curation, but weak integrity and no closed set; rejected in
  favor of an explicit per-model list.
- **C. FK to a `ModelConfigBaseline` table** — strong integrity and free counts, but heavier and a closed
  set; rejected as over-engineered for a soft, UI-level label today.
- **B (chosen)** — JSON allow-list on the model + soft per-asset value, with the constraint applied as a
  **UI dropdown** rather than hard server enforcement.
