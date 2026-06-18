# Asset Management — Model Migration Map

File-by-file mapping from the old Flask/SQLAlchemy application to the new Django application at `app/assets/`.

Old root: `/home/cb/REPOS/asset_management/`
New root: `/home/cb/REPOS/Django-Starter-Kit/`

---

## Old Architecture → New Architecture Summary

| Dimension | Old (Flask/SQLAlchemy) | New (Django ORM) |
| :--- | :--- | :--- |
| Base model | `UserCreatedBase` (SQLAlchemy) | `TraceableMixin + AuditableMixin` (Django mixins from `administration` app) |
| PK type | `Integer` autoincrement | `BigAutoField` — all tables; user-facing IDs rendered as 8-char slugs via integer encrypt/decrypt |
| Access control | `major_location_id` FK | `domain_id` FK → `administration.Domain` |
| M2M through tables | SQLAlchemy association tables | Django through models with audit columns |
| Business layer location | `app/business/` (separate top-level layer) | `app/assets/control_layer/` (inside sub-app) |
| Read layer location | `app/intermediate/` | `app/assets/presentation_layer/search/` |
| Presentation routes | `app/presentation/routes/` | `app/assets/presentation_layer/entrypoints/` |

---

## Core Identity Models

### `app/data/core/asset_info/asset.py` → `app/assets/models/core/asset.py`

**Changes:**
- `major_location_id` → `domain_id` FK to `administration.Domain`
- FK names unchanged: `model_id`, `asset_class_id`
- Old SQLAlchemy `db.Column` declarations → Django field declarations
- Old `@event.listens_for` denormalization listener → moved to `ModelAssetClassPropagationHandler` in control layer (with `# DELIBERATE ANTI-PATTERN` doc on the asset model's `asset_class_id` field)
- `UserCreatedBase` → `TraceableMixin + AuditableMixin`
- `db.relationship()` declarations dropped — Django handles relations through FK declarations + `related_name`

---

### `app/data/core/asset_info/asset_class.py` → `app/assets/models/core/asset_class.py`

**Changes:**
- Add `restrict_to_domain_set` BooleanField (default False)
- Add M2M `domains` through `AssetClassDomain` through model

---

### `app/data/core/asset_info/make_model.py` → `app/assets/models/core/asset_model.py`

**Renamed:** `MakeModel` → `AssetModel`, table `make_models` → `asset_models`

**Changes:**
- Drop `make` CharField — manufacturer is now a separate `Manufacturer` entity linked via M2M
- Rename `model` → `model_name`
- Add `subtype_name` (nullable CharField)
- Keep `revision` CharField (nullable) — repurposed as revision identifier string
- Add `is_base_model` BooleanField (default True)
- Add `base_model_id` self-referential FK (nullable)
- Add M2M `manufacturers` through `ModelManufacturer` through model
- Add M2M `domains` through `ModelDomain` through model
- Drop SQLAlchemy `@event.listens_for` listener for `asset_class_id` propagation — moved to `ModelAssetClassPropagationHandler`

---

### `app/data/core/asset_info/asset_images.py` → `app/assets/models/core/asset_image.py`

**Changes:**
- `VirtualAttachmentReference` base → concrete Django model
- Add `is_primary` BooleanField and `sort_order` PositiveSmallIntegerField

---

### `app/data/core/asset_info/meter_history.py` → `app/assets/models/core/meter_history.py`

**Changes:**
- Add `source` CharField (nullable) — records what triggered the reading (manual, dispatch, maintenance)
- Add `meter_index` field to replace multiple meter-specific tables in old design

---

### New: `app/assets/models/core/manufacturer.py`

**No old equivalent.** Extracted from old `MakeModel.make` CharField.

---

## Asset Sub-Module Models

### `app/data/assets/asset_parent_history.py` → `app/assets/models/asset_parent_history.py`

**Changes:**
- Expand to track both `previous_*` and `new_*` values for parent, root, and depth columns
- Old design only tracked forward state

---

### Capabilities Group

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/data/assets/capabilities/capability_definition.py` | `app/assets/models/capabilities/capability_definition.py` | No structural change |
| `app/data/assets/capabilities/asset_class_capability.py` | `app/assets/models/capabilities/asset_class_capability.py` | No structural change |
| `app/data/assets/capabilities/make_model_capability.py` | `app/assets/models/capabilities/model_capability.py` | Renamed: `MakeModelCapability` → `ModelCapability`; FK renamed `make_model_id` → `model_id` → `AssetModel` |
| `app/data/assets/capabilities/asset_capability.py` | `app/assets/models/capabilities/asset_capability.py` | No structural change |

---

### Configurations Group

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/data/assets/configurations/configuration_template.py` | `app/assets/models/configurations/configuration_template.py` | FK renamed `make_model_id` → `model_id` → `AssetModel` |
| `app/data/assets/configurations/defined_modification.py` | `app/assets/models/configurations/defined_modification.py` | No structural change |
| `app/data/assets/configurations/template_modification.py` | `app/assets/models/configurations/template_modification.py` | No structural change |
| `app/data/assets/configurations/template_child.py` | `app/assets/models/configurations/template_child.py` | FK `child_make_model_id` → `child_model_id` → `AssetModel` |
| `app/data/assets/configurations/asset_configuration.py` | `app/assets/models/configurations/asset_configuration.py` | No structural change |
| `app/data/assets/configurations/actual_modification.py` | `app/assets/models/configurations/actual_modification.py` | No structural change |

---

### Details Group

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/data/assets/details/asset_detail_virtual.py` | `app/assets/models/details/asset_detail_virtual.py` | Convert to Django abstract model; PK is BigAutoField |
| `app/data/assets/details/model_detail_virtual.py` | `app/assets/models/details/model_detail_virtual.py` | Convert to Django abstract model; PK is BigAutoField; FK renamed `make_model_id` → `model_id` |
| `app/data/assets/details/asset_class_details/purchase_info.py` | `app/assets/models/details/asset_class_details/purchase_info.py` | No structural change |
| `app/data/assets/details/asset_class_details/smog_record.py` | `app/assets/models/details/asset_class_details/smog_record.py` | No structural change |
| `app/data/assets/details/asset_class_details/toyota_warranty_receipt.py` | — **Dropped** — | Business-specific; not carried forward. Document if needed as a new detail type |
| `app/data/assets/details/asset_class_details/vehicle_registration.py` | `app/assets/models/details/asset_class_details/vehicle_registration.py` | No structural change |
| `app/data/assets/details/model_details/emissions_info.py` | `app/assets/models/details/model_details/emissions_info.py` | FK rename only |
| `app/data/assets/details/model_details/model_info.py` | `app/assets/models/details/model_details/model_info.py` | FK rename only |
| `app/data/assets/details/detail_table_templates/asset_details_from_asset_class.py` | `app/assets/models/details/detail_table_templates/asset_details_from_asset_class.py` | No structural change |
| `app/data/assets/details/detail_table_templates/asset_details_from_model_type.py` | `app/assets/models/details/detail_table_templates/asset_details_from_model_type.py` | FK rename only |
| `app/data/assets/details/detail_table_templates/model_detail_table_template.py` | `app/assets/models/details/detail_table_templates/model_detail_table_template.py` | FK rename only |

---

## Business / Logic Layer

### Core Business Layer

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/business/core/asset_context.py` → `AssetContext` | `app/assets/control_layer/asset_context.py` | Rewritten for Django patterns; now has Manager sub-properties instead of direct logic |
| `app/business/core/make_model_context.py` → `MakeModelContext` | `app/assets/control_layer/asset_model_context.py` | Renamed `AssetModelContext`; expanded with manufacturer and domain managers |
| `app/business/core/post_create_handlers.py` (ABCs) | `app/assets/control_layer/handlers/` | ABCs preserved as base classes; concrete handlers moved to handlers/ folder |

---

### Assets Business Layer

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/business/assets/capabilities/capability_manager.py` | `app/assets/control_layer/managers/asset_capability_manager.py` | Merged capability management into single manager |
| `app/business/assets/capabilities/capability_factory.py` | Absorbed into `AssetFactory` post-create pipeline | No standalone capability factory needed |
| `app/business/assets/capabilities/handlers.py` (`AssetCapabilityHandler`, `MakeModelCapabilityHandler`) | `handlers/asset_capability_propagation_handler.py`, `handlers/model_capability_propagation_handler.py` | Split into two handlers, one per target entity |
| `app/business/assets/configurations/configuration_manager.py` | `managers/asset_configuration_manager.py` | |
| `app/business/assets/configurations/modification_manager.py` | Merged into `asset_configuration_manager.py` | |
| `app/business/assets/configurations/template_configuration_manager.py` | `managers/template_modification_manager.py` | |
| `app/business/assets/configurations/template_modification_manager.py` | `managers/template_modification_manager.py` | |
| `app/business/assets/configurations/asset_single_layer_configuration_struct.py` | `domain_structs/asset_configuration_struct.py` | |
| `app/business/assets/configurations/template_single_layer_struct.py` | `domain_structs/configuration_template_struct.py` | |
| `app/business/assets/details/asset_details_context.py` | Merged into `asset_context.py` + `managers/asset_detail_manager.py` | |
| `app/business/assets/details/make_model_context.py` | Merged into `asset_model_context.py` | |
| `app/business/assets/details/detail_table_context.py` | `managers/asset_detail_manager.py` | |
| `app/business/assets/details/model_detail_context.py` | `managers/asset_detail_manager.py` (model variant) | |
| `app/business/assets/details/asset_parent_child_relationship_manager.py` | `managers/asset_parent_child_manager.py` | |
| `app/business/assets/details/handlers.py` | `handlers/asset_detail_provisioning_handler.py`, `handlers/model_detail_template_handler.py` | Split |
| `app/business/assets/details/factories/asset_detail_factory.py` | Absorbed into `AssetDetailProvisioningHandler` | |
| `app/business/assets/details/factories/model_detail_factory.py` | Absorbed into `ModelDetailTemplateHandler` | |
| `app/business/assets/details/asset_class_details/asset_details_struct.py` | `domain_structs/asset_struct.py` (detail slice) | |
| `app/business/assets/details/asset_class_details/details_union.py` | `presentation_layer/search/asset_detail_union_search.py` | Moved to search layer (read-only) |
| `app/business/assets/details/model_details/details_union.py` | `presentation_layer/search/model_detail_union_search.py` | Moved to search layer |
| `app/business/assets/details/model_details/model_details_struct.py` | `domain_structs/asset_model_struct.py` (detail slice) | |

---

## Intermediate / Read Layer

| Old | New | Notes |
| :--- | :--- | :--- |
| `app/intermediate/assets/details/asset_detail_union_query.py` | `presentation_layer/search/asset_detail_union_search.py` | Renamed to match new naming convention |
| `app/intermediate/assets/details/model_detail_union_query.py` | `presentation_layer/search/model_detail_union_search.py` | |
| `app/intermediate/assets/configurations/configuration_template_query_provider.py` | `presentation_layer/search/configuration_template_search.py` | |
| `app/intermediate/assets/configurations/defined_modification_query_provider.py` | `presentation_layer/search/defined_modification_search.py` | |
| `app/intermediate/assets/configurations/configuration_events_query_provider.py` | `presentation_layer/search/configuration_events_search.py` | |

---

## Items Not Migrated (Dropped or Deferred)

| Old File | Reason |
| :--- | :--- |
| `app/data/core/asset_info/` — sequence ID managers | SQLAlchemy-specific; Django's BigAutoField handles sequencing; no replacement needed |
| `app/data/core/virtual_sequence_generator.py` | Same reason |
| `app/data/core/sequences/` (all files) | Same reason |
| `app/data/core/build.py` | SQLAlchemy app-factory setup — not applicable in Django |
| `app/data/core/user_info/` | User and auth models live in `administration` app in new project |
| `app/data/core/major_location.py` | Replaced by `administration.Domain` |
| `app/data/core/event_info/` | Events live in `events` app in new project |
| `app/data/core/supply/` | Supply items are a separate sub-application; not in Assets scope |
| `app/data/assets/details/asset_class_details/toyota_warranty_receipt.py` | Business-specific; document as a new detail type when needed |
| `app/business/core/data_insertion_mixin.py` | Replaced by Django model mixins (`TraceableMixin`, `AuditableMixin`) |
| `app/business/core/user_context.py` | User management is in `administration` app |
| `app/business/core/event_context.py` | Event management is in `events` app |
| `app/business/core/user_info/role_manager.py` | RBAC is in `administration` app |

---

## New Target Folder Structure: `app/assets/models/`

```
app/assets/models/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── asset.py
│   ├── asset_class.py
│   ├── asset_model.py
│   ├── manufacturer.py
│   ├── asset_image.py
│   └── meter_history.py
├── asset_parent_history.py
├── capabilities/
│   ├── __init__.py
│   ├── capability_definition.py
│   ├── asset_class_capability.py
│   ├── model_capability.py
│   └── asset_capability.py
├── configurations/
│   ├── __init__.py
│   ├── configuration_template.py
│   ├── defined_modification.py
│   ├── template_modification.py
│   ├── template_child.py
│   ├── asset_configuration.py
│   └── actual_modification.py
├── domain_junctions/
│   ├── __init__.py
│   ├── asset_class_domain.py
│   ├── model_domain.py
│   └── model_manufacturer.py
└── details/
    ├── __init__.py
    ├── asset_detail_virtual.py
    ├── model_detail_virtual.py
    ├── asset_class_details/
    │   ├── __init__.py
    │   ├── purchase_info.py
    │   ├── smog_record.py
    │   └── vehicle_registration.py
    ├── model_details/
    │   ├── __init__.py
    │   ├── emissions_info.py
    │   └── model_info.py
    └── detail_table_templates/
        ├── __init__.py
        ├── asset_details_from_asset_class.py
        ├── asset_details_from_model_type.py
        └── model_detail_table_template.py
```
