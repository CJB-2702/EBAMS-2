# Phase 3 — Control Layer Plan

## Target tree (built)

```
app/assets/control_layer/
├── configurations/
│   ├── configuration_manager.py            # ConfigurationManager
│   ├── configuration_template_manager.py   # ConfigurationTemplateManager
│   ├── template_modification_manager.py    # TemplateModificationManager
│   └── modification_manager.py             # ModificationManager
├── domain_structs/
│   ├── asset_configuration_struct.py       # AssetConfigurationStruct
│   └── configuration_template_struct.py    # ConfigurationTemplateStruct
└── guards/
    └── configuration_assignment_guard.py   # ConfigurationAssignmentValidator
```

## Managers

### ConfigurationManager
Assignment lifecycle for `AssetConfiguration`.

- `assign(asset, template, actor, notes)` — validates via `ConfigurationAssignmentValidator`
  (template active, template.model == asset.model), creates a new `AssetConfiguration`
  (`verification_status='unverified'`, `is_current=True`), emits a "Configuration Assigned"
  event + `AssetEvent` link.  **Multiple configurations per asset are allowed; latest
  wins by `created_at desc`.**  No `is_current` flip on previous rows.
- `update_verification_status(config, new_status)` — 'unverified' | 'partial' | 'complete';
  sets `documented_at` automatically when status transitions to 'complete'.
- `update_notes(config, notes)` — update notes field.
- `get_current(asset)` → most recent `AssetConfiguration` by `created_at desc`.

### ConfigurationTemplateManager
CRUD + revision lifecycle for `ConfigurationTemplate`.

- `create(model, name, revision, description, actor)` — creates template.
- `update(template, name, revision, description, actor)` — updates header fields.
- `deactivate(template, actor)` — sets `is_active=False`.
- `create_new_revision(template, actor)` — clones all `TemplateModification` +
  `TemplateChild` rows into a new template with incremented revision string
  (`major.minor+1`); deactivates the source template atomically.

### TemplateModificationManager
Manages `TemplateModification` and `TemplateChild` records on a template.

- `add_modification(template, defined_mod, context_notes, is_required, actor)` — unique
  constraint enforced with a clear error.
- `remove_modification(template_mod, actor)` — hard-delete the junction row.
- `update_modification(template_mod, context_notes, is_required, actor)`
- `add_child(template, child_model, quantity, is_required, actor)` — guards against
  a template declaring its own model as a child (circular ref).
- `remove_child(template_child, actor)`
- `update_child(template_child, quantity, is_required, actor)`

### ModificationManager
Catalog CRUD + `ActualModification` lifecycle.

- `create_defined_modification(name, code, category, description, actor)` — caller
  provides `code` explicitly (normalized to UPPER); raises on collision.
- `update_defined_modification(defined_mod, ...)` — updates any field; collision check
  on code change.
- `deactivate_defined_modification(defined_mod, actor)` — soft-delete.
- `delete_defined_modification(defined_mod, actor)` — hard-delete only if no references.
- `add_actual_modification(asset, defined_mod, applied_at, notes, actor)` — creates
  "Modification Added" `Event` + `AssetEvent` + links event to `ActualModification.creation_event`.
- `update_actual_modification(actual_mod, applied_at, notes, actor)` — content update, no event.
- `remove_actual_modification(actual_mod, actor)` — creates "Modification Removed" event,
  stores on `removal_event`, sets `is_active=False`.

## Structs

- **`AssetConfigurationStruct.from_asset(asset)`** — current config (latest), resolved
  template, active actual mods, child assets.  Methods: `get_modification_progress()`,
  `get_child_progress()`, `get_undocumented_modifications()`, `get_unmatched_children()`,
  `to_dict()`.
- **`ConfigurationTemplateStruct.from_template(template)`** — template with resolved
  `TemplateModification` and `TemplateChild` rows.  Filter helpers:
  `get_required_modifications()`, `get_optional_modifications()`, `get_required_children()`,
  `get_optional_children()`.

## Guard

- **`ConfigurationAssignmentValidator.check(asset, template)`** — template `is_active`;
  `template.model_id == asset.model_id`.  Called by `ConfigurationManager.assign()` before
  entering the transaction.

## Schema additions (applied)

| Model | Field added |
| :--- | :--- |
| `ConfigurationTemplate` | `revision` CharField(max_length=20, null, blank) |
| `AssetConfiguration` | `verification_status` CharField, choices unverified/partial/complete, default unverified |
| `AssetConfiguration` | `notes` TextField(null, blank) |
| `ActualModification` | `creation_event` FK → events.Event (null, SET_NULL) |
| `ActualModification` | `removal_event` FK → events.Event (null, SET_NULL) |

## Event pattern

All P3 events use:
```python
event = Event.objects.create(
    domain_id=asset.domain_id,
    event_type=EventType.ASSET_MANAGEMENT,
    status=EventStatus.COMPLETE,
    ...
)
AssetEvent.objects.create(asset=asset, event=event, role="configuration"|"modification", ...)
```
Narrator strings centralized in `AssetEventNarrator`:
`configuration_assigned`, `modification_added`, `modification_removed`.

## Decisions from interrogation session (2026-06-04)

- D1: `ConfigurationTemplate.revision` **in scope** — add field + `create_new_revision()`.
- D2: `AssetConfiguration.verification_status` **added back** (unverified/partial/complete).
- D3: `ActualModification` event FKs **added back** — both creation and removal events are
  important audit trail.
- D4: Assignment model — **allow multiple, latest wins** (no atomic `is_current` flip).
- D5: `DefinedModification.code` — **caller provides** explicitly; manager normalizes to UPPER.
