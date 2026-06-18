# Migration Map — old files → new homes

Every file under the old `app/business/core` and `app/business/assets` mapped to
its destination in this project, or flagged superseded / out-of-scope. Use as
the master porting checklist. "Phase" = which sub-kit covers it.

## `app/business/core/`

| Old file | Disposition | New home / note | Phase |
| :--- | :--- | :--- | :--- |
| `asset_context.py` | **Port** | `app/assets/control_layer/` → `AssetContext` + `AssetCreationOrchestrator` + `MeterManager` | 1 |
| `make_model_context.py` | **Port** | `app/assets/control_layer/` → `AssetModelContext` + `AssetModelFactory` (was MakeModel) | 1 |
| `post_create_handlers.py` | **Drop** | Pluggable pipeline rejected (D1). Replaced by explicit orchestrator. See [`../optional_detail_hooking.md`](../optional_detail_hooking.md). | 1 |
| `event_context.py` | **Superseded** | New `events` app already implements comments/attachments/threads. Asset code only *consumes* events + adds the asset↔event link. See [`event_context_study.md`](event_context_study.md). | 1 |
| `data_insertion_mixin.py` | **Drop / out of scope** | SQLAlchemy `from_dict`/`to_dict` mixin. Django uses Structs + Adaptors instead. | — |
| `user_context.py` | **Out of scope** | Belongs to `administration` app, not `assets`. | — |
| `user_info/quicklinks.py` | **Out of scope** | `administration`. | — |
| `user_info/role_manager.py` | **Out of scope** | `administration` (RBAC). | — |
| `factories/` | **Port (folded)** | Old core factories are folded into the new Factories/Orchestrator. | 1 |

## `app/business/assets/`

| Old file | Disposition | New home / note | Phase |
| :--- | :--- | :--- | :--- |
| `details/asset_details_context.py` | **Port** | `AssetDetailsContext` (or merge into `AssetContext` via a `DetailsManager`) | 2 |
| `details/make_model_context.py` | **Port** | `AssetModelDetailsContext` / `DetailsManager` on model | 2 |
| `details/detail_table_context.py` | **Port** | detail provisioning logic vs the template tables | 2 |
| `details/asset_parent_child_relationship_manager.py` | **Port** | `AssetHierarchyManager` (parent/root/depth + `AssetParentHistory`) | 1 |
| `details/factories/asset_detail_factory.py` | **Port** | `AssetDetailFactory` | 2 |
| `details/factories/detail_factory.py` | **Port** | base `DetailFactory` | 2 |
| `details/factories/model_detail_factory.py` | **Port** | `ModelDetailFactory` | 2 |
| `details/handlers.py` | **Port** | detail step handlers | 2 |
| `details/asset_class_details/*` (structs, union) | **Port** | `domain_structs/` for asset details | 2 |
| `details/model_details/*` (struct, union) | **Port** | `domain_structs/` for model details | 2 |
| `configurations/configuration_manager.py` | **Port** | `ConfigurationManager` | 3 |
| `configurations/modification_manager.py` | **Port** | `ModificationManager` (ActualModification) | 3 |
| `configurations/template_configuration_manager.py` | **Port** | `ConfigurationTemplateManager` | 3 |
| `configurations/template_modification_manager.py` | **Port** | `TemplateModificationManager` | 3 |
| `configurations/asset_single_layer_configuration_struct.py` | **Port** | `domain_structs/` | 3 |
| `configurations/template_single_layer_struct.py` | **Port** | `domain_structs/` | 3 |
| `capabilities/capability_factory.py` | **Port** | `CapabilityFactory` (copy-on-create cascade) | 4 |
| `capabilities/capability_manager.py` | **Port** | `CapabilityManager` | 4 |
| `capabilities/handlers.py` | **Port** | capability step handlers | 4 |
| `technical_library/technical_library_manager.py` | **Deferred / out of scope** | No `TechnicalLibraryRecord` model exists in new `assets`. Not in the agreed phase list (P1–P4). Revisit separately. | — |

## Notes

- **Naming:** when porting, rename to the strict suffix vocabulary
  (`docs/Architecture/oop_control_patterns.md`). E.g. old "Manager" that does one
  heavy step → `Handler`; old "Context" that loads + delegates → keep `Context`
  but back it with a `Struct`.
- **`MakeModel` → `AssetModel`** in every ported file, plus `make` (string) →
  `Manufacturer` relation where the old code used it.
- **`major_location_id` → `domain_id`** in every ported file.
- **`technical_library`** and **user/event/role** logic are intentionally **not**
  in this kit's four phases; do not pull them into `app/assets` without a new
  decision.
