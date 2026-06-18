# Phase 3 — Old → New Migration Notes

## Source files

- `app/business/assets/configurations/configuration_manager.py`
- `app/business/assets/configurations/modification_manager.py`
- `app/business/assets/configurations/template_configuration_manager.py`
- `app/business/assets/configurations/template_modification_manager.py`
- `app/business/assets/configurations/asset_single_layer_configuration_struct.py`
- `app/business/assets/configurations/template_single_layer_struct.py`

## Mapping

| Old | New | Change |
| :--- | :--- | :--- |
| `ConfigurationManager` | `ConfigurationManager` | Keep; one-current-per-asset enforced in one atomic block; events via Phase 1 seam (was direct `Event(...)`). |
| `template_configuration_manager.py` | `ConfigurationTemplateManager` | Template + `TemplateChild` CRUD. |
| `template_modification_manager.py` | `TemplateModificationManager` | `TemplateModification` ↔ `DefinedModification`. |
| `modification_manager.py` | `ModificationManager` | `ActualModification` + `DefinedModification` catalog. |
| `asset_single_layer_configuration_struct.py` | `AssetConfigurationStruct` | Read model; expected-vs-actual join. |
| `template_single_layer_struct.py` | `ConfigurationTemplateStruct` | Read model. |

## Behavioral notes

- **`is_current` flip** is the central invariant — assigning a template must
  demote the previous current configuration atomically. Verify the old code's
  exact rule (one current vs. allowing none) and preserve it.
- **Modification catalog vs. actuals:** old code distinguished defined
  (catalog) vs. actual (per-asset). Map cleanly: `DefinedModification` is the
  catalog, `ActualModification` is per-asset, `TemplateModification` is the
  expected set on a template.
- The old configuration manager created **configuration events** — route those
  through Phase 1's `AssetEventNarrator` + `AssetEvent`, not a direct `Event`
  with `asset_id`.

## Watch-outs

- `DefinedModification.code` is unique — catalog create must handle/raise on
  collision.
- `ConfigurationTemplate.model` and `TemplateChild.child_model` are `PROTECT` —
  manager deletes must account for referenced rows.
- Decide explicitly whether assigning a template **auto-creates expected child
  assets**. Default in this kit: **no** (track expectation only). If yes later,
  it's an orchestrator step, not buried in the manager.

## Drop / avoid

- SQLAlchemy `db.session` independent commits.
- `make_model` / `major_location` references → `AssetModel` / `domain`.
