---
type: "Technical Decision"
title: "Asset Management — Control Layer Architecture Plan"
description: "This document maps the service architecture: Structs, Contexts, Managers, Handlers, Factories, Guards, and Adaptors for the app/assets/ control layer."
tags: [technical-decisions, technical-decision, project-history, assets-migration-project]
context_tier: 2
---

# Asset Management — Control Layer Architecture Plan

This document maps the service architecture: Structs, Contexts, Managers, Handlers, Factories, Guards, and Adaptors for the `app/assets/` control layer.

Naming follows the project's OOP suffix vocabulary (`harness/Architecture/patterns/oop_control_patterns.md`). File paths are relative to `app/assets/control_layer/`.

---

## 1. Domain Structs

Defined in `control_layer/domain_structs/`. These are typed read-only aggregates. They do not mutate state.

| Struct | File | What It Loads |
| :--- | :--- | :--- |
| `AssetStruct` | `domain_structs/asset_struct.py` | Base asset row + domain + model (with class) + current capability_status. Optional eager: capabilities, configurations, detail row summary |
| `AssetModelStruct` | `domain_structs/asset_model_struct.py` | Model row + manufacturers (M2M) + domains (M2M) + asset class + revision chain (base model or variants list). Optional eager: capabilities, configuration templates |
| `AssetClassStruct` | `domain_structs/asset_class_struct.py` | Class row + domains (M2M) + restrict_to_domain_set flag. Optional eager: capabilities defined for class |
| `ManufacturerStruct` | `domain_structs/manufacturer_struct.py` | Manufacturer row. Optional eager: all models linked to this manufacturer |
| `CapabilityStruct` | `domain_structs/capability_struct.py` | `CapabilityDefinition` row + optional: class assignments, model assignments, asset assignments |
| `ConfigurationTemplateStruct` | `domain_structs/configuration_template_struct.py` | Template row + model + all `TemplateModification` rows (with `DefinedModification`) + all `TemplateChild` rows |
| `AssetConfigurationStruct` | `domain_structs/asset_configuration_struct.py` | `AssetConfiguration` row + expanded `ConfigurationTemplateStruct` + `ActualModification` rows on the asset — used to compute compliance state |

---

## 2. Contexts

Contexts are the primary entry point for control operations. Each Context accepts a natural key (usually an `id`), loads the appropriate Struct, and exposes domain-verb methods. All contexts expose `from_struct()` for callers that already hold the Struct.

---

### 2.1 `AssetContext`

**File:** `asset_context.py`

Entry point for all operations on a single asset.

```
AssetContext(asset_id, eager=False)
  .struct → AssetStruct
  .from_struct(struct) → AssetContext
```

**Mutations exposed:**
- `update_status(status)` — updates `asset.status` via `StateMachine` gate
- `update_domain(domain_id)` — delegates to `AssetDomainManager`
- `update_model(model_id)` — delegates to `AssetModelAssignmentManager`
- `set_parent(parent_asset_id)` — delegates to `AssetParentChildManager`
- `detach_from_parent()` — delegates to `AssetParentChildManager`
- `record_meter_reading(meter_index, value, recorded_at, source)` — delegates to `AssetMeterManager`
- `deactivate()` — soft-deactivate with event emission

**Sub-managers (properties):**

| Manager | Property | Responsibility |
| :--- | :--- | :--- |
| `AssetDomainManager` | `.domain` | Validates and applies domain changes; enforces `AssetClass.restrict_to_domain_set` |
| `AssetCapabilityManager` | `.capabilities` | Activate/deactivate asset capabilities; propagate from model/class |
| `AssetConfigurationManager` | `.configuration` | Assign templates, record actual modifications, compute compliance |
| `AssetDetailManager` | `.details` | Provision, read, update extensible detail rows |
| `AssetMeterManager` | `.meters` | Record readings, update live meter values on asset |
| `AssetParentChildManager` | `.hierarchy` | Set/clear parent, update root/depth, write `AssetParentHistory` |

---

### 2.2 `AssetModelContext`

**File:** `asset_model_context.py`

Entry point for model definition management.

```
AssetModelContext(model_id, eager=False)
  .struct → AssetModelStruct
```

**Mutations exposed:**
- `update_asset_class(asset_class_id)` — class change triggers `Asset.asset_class_id` cascade via `ModelAssetClassPropagationHandler`
- `add_manufacturer(manufacturer_id, is_primary)` — delegates to `ModelManufacturerManager`
- `remove_manufacturer(manufacturer_id)` — delegates to `ModelManufacturerManager`
- `add_domain(domain_id)` — delegates to `ModelDomainManager`
- `remove_domain(domain_id)` — delegates to `ModelDomainManager`
- `create_revision(model_name, subtype_name, revision)` → new `AssetModel` with `is_base_model=False`, `base_model_id=self`

**Sub-managers:**

| Manager | Property | Responsibility |
| :--- | :--- | :--- |
| `ModelManufacturerManager` | `.manufacturers` | M2M manufacturer assignment, primary flag |
| `ModelDomainManager` | `.domains` | M2M domain assignment |
| `ModelCapabilityManager` | `.capabilities` | Capability assignment to model; propagates to linked assets |

---

### 2.3 `AssetClassContext`

**File:** `asset_class_context.py`

Entry point for asset class management.

```
AssetClassContext(asset_class_id, eager=False)
  .struct → AssetClassStruct
```

**Mutations exposed:**
- `add_domain(domain_id)` — delegates to `AssetClassDomainManager`
- `remove_domain(domain_id)` — delegates to `AssetClassDomainManager` (enforces minimum-one constraint)
- `set_restrict_to_domain_set(value: bool)` — updates flag
- `add_capability(capability_definition_id)` — delegates to `AssetClassCapabilityManager`
- `remove_capability(capability_definition_id)` — delegates to `AssetClassCapabilityManager`

**Sub-managers:**

| Manager | Property | Responsibility |
| :--- | :--- | :--- |
| `AssetClassDomainManager` | `.domains` | Domain M2M management; enforces at-least-one-domain invariant |
| `AssetClassCapabilityManager` | `.capabilities` | Class-level capability catalog management |

---

### 2.4 `ConfigurationTemplateContext`

**File:** `configuration_template_context.py`

Entry point for configuration template management.

```
ConfigurationTemplateContext(template_id, eager=False)
  .struct → ConfigurationTemplateStruct
```

**Sub-managers:**

| Manager | Property | Responsibility |
| :--- | :--- | :--- |
| `TemplateModificationManager` | `.modifications` | Add/remove/update `TemplateModification` rows |
| `TemplateChildManager` | `.children` | Add/remove `TemplateChild` rows |

---

## 3. Managers

Managers are stable collaborators on their parent Context. They receive the Context's Struct (or Context itself) and own a sub-area of operations.

| Manager | File | Parent Context | Key Operations |
| :--- | :--- | :--- | :--- |
| `AssetDomainManager` | `managers/asset_domain_manager.py` | AssetContext | `set_domain(domain_id)` — validates against AssetClass restriction; writes to `asset.domain_id` |
| `AssetCapabilityManager` | `managers/asset_capability_manager.py` | AssetContext | `activate(cap_def_id)`, `deactivate(cap_def_id)`, `propagate_from_model()` |
| `AssetConfigurationManager` | `managers/asset_configuration_manager.py` | AssetContext | `assign_template(template_id)`, `add_modification(defined_mod_id)`, `remove_modification(actual_mod_id)`, `compute_compliance_status()` |
| `AssetDetailManager` | `managers/asset_detail_manager.py` | AssetContext | `provision_for_asset()`, `get_all_rows()`, `update_row(table_name, row_id, data)` |
| `AssetMeterManager` | `managers/asset_meter_manager.py` | AssetContext | `record_reading(index, value, recorded_at, source)`, `get_history(index)` |
| `AssetParentChildManager` | `managers/asset_parent_child_manager.py` | AssetContext | `set_parent(parent_id)`, `detach()`, `recompute_tree()`, writes `AssetParentHistory` |
| `ModelManufacturerManager` | `managers/model_manufacturer_manager.py` | AssetModelContext | `add(mfr_id, is_primary)`, `remove(mfr_id)`, `set_primary(mfr_id)` |
| `ModelDomainManager` | `managers/model_domain_manager.py` | AssetModelContext | `add(domain_id)`, `remove(domain_id)` |
| `ModelCapabilityManager` | `managers/model_capability_manager.py` | AssetModelContext | `add(cap_def_id)`, `remove(cap_def_id)`, `sync_to_linked_assets()` |
| `AssetClassDomainManager` | `managers/asset_class_domain_manager.py` | AssetClassContext | `add(domain_id)`, `remove(domain_id)` — blocks removal if it would leave zero domains |
| `AssetClassCapabilityManager` | `managers/asset_class_capability_manager.py` | AssetClassContext | `add(cap_def_id)`, `remove(cap_def_id)` |
| `TemplateModificationManager` | `managers/template_modification_manager.py` | ConfigurationTemplateContext | `add(defined_mod_id, context_notes, is_required)`, `remove(template_mod_id)`, `update(template_mod_id, data)` |
| `TemplateChildManager` | `managers/template_child_manager.py` | ConfigurationTemplateContext | `add(child_model_id, quantity, is_required)`, `remove(template_child_id)` |

---

## 4. Factories

Factories handle root-entity creation. They are stateless class-method-only classes. Entry path: route → Adaptor → Factory.

| Factory | File | Creates |
| :--- | :--- | :--- |
| `AssetFactory` | `asset_factory.py` | Root `Asset` row + runs post-create handler pipeline (detail rows, capability propagation) |
| `AssetModelFactory` | `asset_model_factory.py` | `AssetModel` row + initial manufacturer M2M rows + initial domain M2M rows |
| `AssetClassFactory` | `asset_class_factory.py` | `AssetClass` row + initial domain M2M (at least one required) |
| `ManufacturerFactory` | `manufacturer_factory.py` | `Manufacturer` row |
| `ConfigurationTemplateFactory` | `configuration_template_factory.py` | `ConfigurationTemplate` row for a given model |
| `DefinedModificationFactory` | `defined_modification_factory.py` | `DefinedModification` catalog entry |

---

## 5. Handlers (Post-Create Pipeline)

Handlers run after root entity creation. They are registered in a pipeline executed by the Factory after the base row is persisted. Each handler does one job.

| Handler | File | Trigger | What It Does |
| :--- | :--- | :--- | :--- |
| `AssetDetailProvisioningHandler` | `handlers/asset_detail_provisioning_handler.py` | After `AssetFactory` creates an Asset | Queries `AssetDetailTemplateByAssetClass` and `AssetDetailTemplateByModelType`; creates the appropriate concrete detail rows; marks `asset.detail_rows_created` |
| `AssetCapabilityPropagationHandler` | `handlers/asset_capability_propagation_handler.py` | After `AssetFactory` creates an Asset | Copies active capabilities from `AssetClassCapability` and `ModelCapability` to `AssetCapability` rows for the new asset |
| `ModelCapabilityPropagationHandler` | `handlers/model_capability_propagation_handler.py` | After `AssetModelFactory` creates an AssetModel | Copies capabilities from the linked `AssetClass` into `ModelCapability` rows for the new model |
| `ModelDetailTemplateHandler` | `handlers/model_detail_template_handler.py` | After `AssetModelFactory` creates an AssetModel | Creates `ModelDetailTableTemplate` rows based on the model's `AssetClass` configuration |
| `ModelAssetClassPropagationHandler` | `handlers/model_asset_class_propagation_handler.py` | When `AssetModelContext.update_asset_class()` is called | Bulk-updates `asset.asset_class_id` for all assets linked to this model — DELIBERATE ANTI-PATTERN: documented cascade |

---

## 6. Guards

Guards constrain control flow. All guard files end in `_guard.py`.

### Policies (authorization: "may this happen?")

| Class | File | Guards |
| :--- | :--- | :--- |
| `AssetDomainAccessPolicy` | `guards/asset_domain_access_guard.py` | Checks `asset.domain_id in user.assigned_domain_ids` before any read or write on an Asset |
| `AssetClassDomainRestrictionPolicy` | `guards/asset_class_domain_restriction_guard.py` | When `AssetClass.restrict_to_domain_set=True`, checks that the target `domain_id` is in the class's domain set before assigning an asset |

### Validators (input and invariant checks)

| Class | File | Validates |
| :--- | :--- | :--- |
| `AssetClassMinimumDomainValidator` | `guards/asset_class_minimum_domain_guard.py` | Prevents removing the last domain from an `AssetClass.domains` — must always have at least one |
| `ModelRevisionTreeValidator` | `guards/model_revision_tree_guard.py` | Enforces that a revision's `base_model_id` must point to a base model (`is_base_model=True`); prevents multi-level nesting |
| `AssetSerialNumberValidator` | `guards/asset_serial_number_guard.py` | Validates serial number uniqueness and format at create/update boundaries |

### State Machines (status transitions)

| Class | File | Entity | Legal Transitions |
| :--- | :--- | :--- | :--- |
| `AssetStatusStateMachine` | `guards/asset_status_guard.py` | `Asset.status` | Active → Inactive, Active → Decommissioned; Inactive → Active; no transition back from Decommissioned |

---

## 7. Adaptors

Adaptors map raw HTTP form/POST data into structured inputs the control layer understands. They live in `control_layer/adapters/`.

| Adaptor | File | Maps |
| :--- | :--- | :--- |
| `CreateAssetAdaptor` | `adapters/create_asset_adaptor.py` | POST form → `AssetFactory` kwargs: name, serial_number, model_id, domain_id |
| `UpdateAssetAdaptor` | `adapters/update_asset_adaptor.py` | POST form → dict for `AssetContext` mutation methods |
| `CreateAssetModelAdaptor` | `adapters/create_asset_model_adaptor.py` | POST form → `AssetModelFactory` kwargs |
| `CreateAssetClassAdaptor` | `adapters/create_asset_class_adaptor.py` | POST form → `AssetClassFactory` kwargs + initial domain list |
| `AssignConfigurationTemplateAdaptor` | `adapters/assign_configuration_template_adaptor.py` | POST form → `AssetConfigurationManager.assign_template()` args |
| `RecordMeterReadingAdaptor` | `adapters/record_meter_reading_adaptor.py` | POST form → `AssetMeterManager.record_reading()` args; validates meter_index range (1–4) and value type |

---

## 8. Delegation Flow — End-to-End Example

**Scenario: Assign a new domain to an asset**

```
HTTP POST /assets/{id}/domain/
  → entrypoint (thin: parse request, check permissions)
      → UpdateAssetAdaptor.clean_domain_data(request.POST)
          → AssetContext(asset_id).update_domain(domain_id)
              → AssetClassDomainRestrictionPolicy.check(asset, domain_id)  [guard]
              → AssetDomainManager(struct).set_domain(domain_id)
                  → Asset.save()  [ORM write — control layer only]
  ← HTTP 200 / redirect
```

**Scenario: Create a new asset**

```
HTTP POST /assets/create/
  → entrypoint
      → CreateAssetAdaptor.from_request(request.POST) → kwargs
          → AssetFactory.create(**kwargs)
              → Asset.objects.create(...)  [ORM write]
              → AssetDetailProvisioningHandler.run(asset)
              → AssetCapabilityPropagationHandler.run(asset)
          → return AssetStruct(asset.id)
  ← HTTP redirect to asset detail
```

---

## 9. File Structure (control_layer/)

```
app/assets/control_layer/
├── adapters/
│   ├── create_asset_adaptor.py
│   ├── update_asset_adaptor.py
│   ├── create_asset_model_adaptor.py
│   ├── create_asset_class_adaptor.py
│   ├── assign_configuration_template_adaptor.py
│   └── record_meter_reading_adaptor.py
├── domain_structs/
│   ├── asset_struct.py
│   ├── asset_model_struct.py
│   ├── asset_class_struct.py
│   ├── manufacturer_struct.py
│   ├── capability_struct.py
│   ├── configuration_template_struct.py
│   └── asset_configuration_struct.py
├── guards/
│   ├── asset_domain_access_guard.py
│   ├── asset_class_domain_restriction_guard.py
│   ├── asset_class_minimum_domain_guard.py
│   ├── model_revision_tree_guard.py
│   ├── asset_serial_number_guard.py
│   └── asset_status_guard.py
├── handlers/
│   ├── asset_detail_provisioning_handler.py
│   ├── asset_capability_propagation_handler.py
│   ├── model_capability_propagation_handler.py
│   ├── model_detail_template_handler.py
│   └── model_asset_class_propagation_handler.py
├── managers/
│   ├── asset_domain_manager.py
│   ├── asset_capability_manager.py
│   ├── asset_configuration_manager.py
│   ├── asset_detail_manager.py
│   ├── asset_meter_manager.py
│   ├── asset_parent_child_manager.py
│   ├── model_manufacturer_manager.py
│   ├── model_domain_manager.py
│   ├── model_capability_manager.py
│   ├── asset_class_domain_manager.py
│   ├── asset_class_capability_manager.py
│   ├── template_modification_manager.py
│   └── template_child_manager.py
├── asset_context.py
├── asset_model_context.py
├── asset_class_context.py
├── configuration_template_context.py
├── asset_factory.py
├── asset_model_factory.py
├── asset_class_factory.py
├── manufacturer_factory.py
├── configuration_template_factory.py
└── defined_modification_factory.py
```
