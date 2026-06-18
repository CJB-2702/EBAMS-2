# Phase 3 — Data & Relational Plan

*All models below are **built**. No schema added this phase.*

## Entities

| Model | `db_table` | Key fields | Relationships |
| :--- | :--- | :--- | :--- |
| `ConfigurationTemplate` | `configuration_template` | `name`, `description`, `is_active` | FK `model`→AssetModel (PROTECT) |
| `TemplateChild` | `template_child` | `quantity`, `is_required` | FK `parent_template`→ConfigurationTemplate (CASCADE); FK `child_model`→AssetModel (PROTECT) |
| `TemplateModification` | `template_modification` | `context_notes`, `is_required` | FK `template` (CASCADE); FK `defined_modification` (PROTECT); unique(template, defined_modification) |
| `DefinedModification` | `defined_modification` | `name`, `code` (unique), `category`, `is_active` | catalog root |
| `AssetConfiguration` | `asset_configuration` | `documented_at`, `is_current` | FK `asset`→Asset (CASCADE); FK `template`→ConfigurationTemplate (PROTECT) |
| `ActualModification` | `actual_modification` | `applied_at`, `notes`, `is_active` | FK `asset`→Asset (CASCADE); FK `defined_modification`→DefinedModification (PROTECT) |

## Relational flow

```
AssetModel ─1──< ConfigurationTemplate ─1──< TemplateChild ─*──1 AssetModel (child_model)
                                  └────1──< TemplateModification ─*──1 DefinedModification
                                                                          │
Asset ─1──< AssetConfiguration ─*──1 ConfigurationTemplate                │
Asset ─1──< ActualModification ─*──────────────────────────────1 DefinedModification
```

## Invariants the control layer must enforce

1. **One current configuration per asset.** Assigning a new template sets the
   previous `AssetConfiguration.is_current = False` and the new one `True`
   (atomic). Old `ConfigurationManager` owned this.
2. **Catalog integrity.** `ActualModification` and `TemplateModification` only
   reference `is_active` (or at least existing) `DefinedModification` rows;
   `code` is unique.
3. **Template/model coherence.** A `ConfigurationTemplate.model` and its
   `TemplateChild.child_model` are valid `AssetModel`s; deleting a referenced
   model is `PROTECT`ed.

## Open data question

`TemplateChild` declares *expected* child assets by model + quantity. Phase 3
**tracks** expectation; it does not necessarily instantiate child `Asset` rows.
If auto-instantiation is desired later, that becomes an orchestrator step (P1
seam) — out of scope unless decided.
