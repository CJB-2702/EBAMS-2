# Asset Management — Data Relational Plan

All tables carry the standard project audit columns: `created_at`, `updated_at`, `created_by_id` (FK → User), `updated_by_id` (FK → User). These are omitted from individual table listings below for brevity.

All primary keys are `BigAutoField` integers. User-facing identifiers are rendered as 8-character slugs via an integer encrypt/decrypt function — no UUID keys are used anywhere in this application.

`Domain` is owned by the `administration` app — it is referenced here as a FK target only.

---

## Relational Overview

```
                  ┌─────────────┐
                  │  AssetClass │
                  │ (domain_set)│
                  └──────┬──────┘
                         │ FK
                  ┌──────▼──────┐
    Manufacturer  │  AssetModel │  (self-ref revision tree)
    (M2M via      │ (domain_set)│
    ModelMfr)     └──────┬──────┘
                         │ FK
               ┌─────────▼──────────┐
               │       Asset        │
               │ (domain_id: single)│
               │ (parent/root tree) │
               └────────┬───────────┘
            ┌───────────┼──────────────┐
            │           │              │
     AssetImage   MeterHistory   AssetParentHistory
            │
    (→ events.Attachment)
```

---

## 1. Core Identity Models

### 1.1 `AssetClass`

Broad category of asset (e.g. Generator, Pump, Light Vehicle).

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(100) | unique |
| `description` | TextField | nullable |
| `category` | CharField(100) | nullable, free grouping |
| `is_active` | BooleanField | default True |
| `restrict_to_domain_set` | BooleanField | default False — if True, assets of this class may only be placed in domains from this class's domain set |

**Relations:**
- M2M → `Domain` (via `AssetClassDomain` — see §4)
- One-to-many → `AssetModel`

**Constraints:**
- Must have at least one `Domain` assigned (enforced in control layer `Validator`)

---

### 1.2 `Manufacturer`

A company that produces asset models. Extracted from the old flat `MakeModel.make` field.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(200) | unique |
| `code` | CharField(50) | unique, nullable — short code for display |
| `website` | URLField | nullable |
| `is_active` | BooleanField | default True |

**Relations:**
- M2M → `AssetModel` (via `ModelManufacturer` — see §4)

---

### 1.3 `AssetModel`

Product definition for a type of asset. Replaces the old `MakeModel`. Supports a self-referential revision tree.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `model_name` | CharField(200) | primary product name |
| `subtype_name` | CharField(200) | nullable — variant/subtype designation |
| `revision` | CharField(100) | nullable — revision identifier string |
| `is_base_model` | BooleanField | default True — False for revision variants |
| `base_model_id` | FK → `AssetModel` | nullable — NULL when is_base_model=True |
| `asset_class_id` | FK → `AssetClass` | |
| `meter1_unit` | CharField(100) | nullable |
| `meter2_unit` | CharField(100) | nullable |
| `meter3_unit` | CharField(100) | nullable |
| `meter4_unit` | CharField(100) | nullable |
| `is_active` | BooleanField | default True |

**Relations:**
- M2M → `Manufacturer` (via `ModelManufacturer` — see §4)
- M2M → `Domain` (via `ModelDomain` — see §4)
- Self-referential FK: `base_model_id` → `AssetModel` (revision tree)
- One-to-many → `Asset`

**Revision tree rule:** A revision (`is_base_model=False`) must reference a base model that has `is_base_model=True`. Nesting revisions under revisions is not permitted (enforced in control layer `Validator`).

---

### 1.4 `Asset`

A physical (or virtual) tracked entity.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(100) | |
| `serial_number` | CharField(100) | unique |
| `status` | CharField(50) | default `'Active'` |
| `capability_status` | CharField(20) | nullable |
| `is_active` | BooleanField | default True |
| `domain_id` | FK → `Domain` | single domain assignment — replaces old major_location_id |
| `model_id` | FK → `AssetModel` | |
| `asset_class_id` | FK → `AssetClass` | denormalized — propagated from AssetModel on save (DELIBERATE ANTI-PATTERN; critical integrity field) |
| `root_asset_id` | FK → `Asset` | nullable, self-ref |
| `parent_asset_id` | FK → `Asset` | nullable, self-ref |
| `depth_from_root` | PositiveSmallIntegerField | nullable |
| `meter1` | FloatField | nullable |
| `meter2` | FloatField | nullable |
| `meter3` | FloatField | nullable |
| `meter4` | FloatField | nullable |
| `tags` | JSONField | nullable — use sparingly |
| `detail_rows_created` | JSONField | nullable — tracks which detail table rows have been provisioned |

**Relations:**
- FK → `Domain`
- FK → `AssetModel`
- FK → `AssetClass` (denormalized)
- Self-ref FK × 2: `root_asset_id`, `parent_asset_id`
- One-to-many → `AssetImage`
- One-to-many → `MeterHistory`
- One-to-many → `AssetParentHistory`

**Note on `asset_class_id` denormalization:** When `AssetModel.asset_class_id` changes, all assets linked to that model must have their `asset_class_id` updated. This is a DELIBERATE ANTI-PATTERN carried over from the original design because the integrity cost of letting these drift outweighs the anti-pattern cost. Enforced in the control layer `AssetModelContext`.

---

### 1.5 `AssetImage`

Links a file attachment (owned by the `events` app) to an asset.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `attachment_id` | FK → `events.Attachment` | |
| `is_primary` | BooleanField | default False — one image can be the hero image |
| `sort_order` | PositiveSmallIntegerField | default 0 |

---

### 1.6 `MeterHistory`

Records a meter reading at a point in time.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `meter_index` | PositiveSmallIntegerField | 1–4 |
| `value` | FloatField | |
| `recorded_at` | DateTimeField | |
| `source` | CharField(50) | nullable — 'manual', 'dispatch', 'maintenance', etc. |

---

### 1.7 `AssetParentHistory`

Audit trail for parent-child relationship changes on an asset.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `previous_parent_asset_id` | FK → `Asset` | nullable |
| `new_parent_asset_id` | FK → `Asset` | nullable |
| `previous_root_asset_id` | FK → `Asset` | nullable |
| `new_root_asset_id` | FK → `Asset` | nullable |
| `previous_depth` | PositiveSmallIntegerField | nullable |
| `new_depth` | PositiveSmallIntegerField | nullable |

---

## 2. Capabilities

### 2.1 `CapabilityDefinition`

Catalog of capabilities that can be assigned to asset classes, models, and individual assets.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(200) | unique |
| `code` | CharField(50) | unique |
| `description` | TextField | nullable |
| `is_active` | BooleanField | default True |

---

### 2.2 `AssetClassCapability`

Capabilities that are available to an asset class (template layer).

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_class_id` | FK → `AssetClass` | |
| `capability_definition_id` | FK → `CapabilityDefinition` | |
| `is_active` | BooleanField | default True |

Unique constraint: `(asset_class_id, capability_definition_id)`.

---

### 2.3 `ModelCapability`

Capabilities at the model level. Replaces old `MakeModelCapability`.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `model_id` | FK → `AssetModel` | |
| `capability_definition_id` | FK → `CapabilityDefinition` | |
| `is_active` | BooleanField | default True |

Unique constraint: `(model_id, capability_definition_id)`.

---

### 2.4 `AssetCapability`

Actual capability assignment on a specific asset instance.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `capability_definition_id` | FK → `CapabilityDefinition` | |
| `is_active` | BooleanField | default True |
| `notes` | TextField | nullable |

Unique constraint: `(asset_id, capability_definition_id)`.

---

## 3. Configurations

### 3.1 `ConfigurationTemplate`

Standard build specification for a model. Defines expected modifications and child assets.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(200) | |
| `description` | TextField | nullable |
| `model_id` | FK → `AssetModel` | |
| `is_active` | BooleanField | default True |

---

### 3.2 `DefinedModification`

Reusable catalog entry for a standardized modification (e.g. "Level 3 Hydraulic Upgrade").

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `name` | CharField(200) | |
| `code` | CharField(50) | unique |
| `description` | TextField | nullable |
| `category` | CharField(100) | nullable |
| `is_active` | BooleanField | default True |

---

### 3.3 `TemplateModification`

Junction: links a `DefinedModification` to a `ConfigurationTemplate` with context.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `template_id` | FK → `ConfigurationTemplate` | |
| `defined_modification_id` | FK → `DefinedModification` | |
| `context_notes` | TextField | nullable — notes specific to this template |
| `is_required` | BooleanField | default False |

Unique constraint: `(template_id, defined_modification_id)`.

---

### 3.4 `TemplateChild`

Declares an expected child asset within a configuration template.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `parent_template_id` | FK → `ConfigurationTemplate` | |
| `child_model_id` | FK → `AssetModel` | expected child model |
| `quantity` | PositiveSmallIntegerField | default 1 |
| `is_required` | BooleanField | default False |

---

### 3.5 `AssetConfiguration`

Links an asset to a configuration template, tracking documentation status.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `template_id` | FK → `ConfigurationTemplate` | |
| `documented_at` | DateTimeField | nullable |
| `is_current` | BooleanField | default True |

---

### 3.6 `ActualModification`

Documents a real modification present on a specific asset.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |
| `defined_modification_id` | FK → `DefinedModification` | |
| `applied_at` | DateField | nullable |
| `notes` | TextField | nullable |
| `is_active` | BooleanField | default True |

---

## 4. Domain Junction Tables

These are M2M through tables carrying audit columns so domain assignment history can be queried.

### 4.1 `AssetClassDomain`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_class_id` | FK → `AssetClass` | |
| `domain_id` | FK → `Domain` | |

Unique: `(asset_class_id, domain_id)`.

---

### 4.2 `ModelDomain`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `model_id` | FK → `AssetModel` | |
| `domain_id` | FK → `Domain` | |

Unique: `(model_id, domain_id)`.

---

### 4.3 `ModelManufacturer`

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `model_id` | FK → `AssetModel` | |
| `manufacturer_id` | FK → `Manufacturer` | |
| `is_primary` | BooleanField | default False — one manufacturer can be designated primary |

Unique: `(model_id, manufacturer_id)`.

---

## 5. Detail Tables (Extensible Per-Class / Per-Model Data)

### 5.1 `AssetDetailVirtual` (abstract Django model)

Base class for all asset-specific detail tables. Concrete tables inherit from this.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `asset_id` | FK → `Asset` | |

---

### 5.2 `ModelDetailVirtual` (abstract Django model)

Base class for all model-specific detail tables.

| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | BigAutoField PK | |
| `model_id` | FK → `AssetModel` | |

---

### 5.3 Concrete Detail Tables (Asset-Level)

These inherit `AssetDetailVirtual`. New ones can be added per asset class.

| Table | Extra Fields | Asset Class Scope |
| :--- | :--- | :--- |
| `PurchaseInfo` | `purchase_date`, `purchase_price`, `vendor`, `purchase_order_number` | Any |
| `VehicleRegistration` | `plate_number`, `registration_expiry`, `state_province`, `vin_number` | Vehicle |
| `SmogRecord` | `test_date`, `test_result`, `test_station`, `certificate_number`, `expiry_date` | Vehicle |

---

### 5.4 Concrete Detail Tables (Model-Level)

These inherit `ModelDetailVirtual`.

| Table | Extra Fields | Model Scope |
| :--- | :--- | :--- |
| `ModelInfo` | `engine_type`, `horsepower`, `weight_kg`, `length_mm`, `width_mm`, `height_mm` | General |
| `EmissionsInfo` | `emissions_standard`, `tier_level`, `co2_rating`, `certified_year` | Vehicle/Engine |

---

### 5.5 Detail Table Template Configuration

These control which detail tables get provisioned for new assets based on class/model.

| Table | Purpose |
| :--- | :--- |
| `AssetDetailTemplateByAssetClass` | Specifies which `AssetDetailVirtual` subclasses are created for assets of a given `AssetClass` |
| `AssetDetailTemplateByModelType` | Specifies additional `AssetDetailVirtual` subclasses based on the specific `AssetModel` |
| `ModelDetailTableTemplate` | Specifies which `ModelDetailVirtual` subclasses are created for a given `AssetModel` |

---

## 6. Entity Relationship Summary

```
Division → Organization → Domain   [administration app]
                               ↑
                    AssetClass (M2M → Domain, restrict_to_domain_set bool)
                               ↑
              Manufacturer (M2M) ← AssetModel → Domain (M2M)
                               ↑
                            Asset → Domain (single FK)
                               ↑
            ┌──────────────────┼─────────────────────┐
    AssetImage          MeterHistory         AssetParentHistory
    (→ events.Attachment)

AssetClass ← AssetClassCapability ← CapabilityDefinition
AssetModel ← ModelCapability ← CapabilityDefinition
Asset      ← AssetCapability  ← CapabilityDefinition

AssetModel ← ConfigurationTemplate
               ↓
         TemplateModification → DefinedModification
         TemplateChild        → AssetModel (expected child)

Asset ← AssetConfiguration → ConfigurationTemplate
Asset ← ActualModification  → DefinedModification

Asset ← PurchaseInfo (AssetDetailVirtual)
Asset ← VehicleRegistration (AssetDetailVirtual)
Asset ← SmogRecord (AssetDetailVirtual)

AssetModel ← ModelInfo (ModelDetailVirtual)
AssetModel ← EmissionsInfo (ModelDetailVirtual)
```

---

## 7. Table Count Summary

| Group | Table Count |
| :--- | :--- |
| Core identity (Asset, AssetClass, AssetModel, Manufacturer) | 4 |
| Core support (AssetImage, MeterHistory, AssetParentHistory) | 3 |
| Domain junctions (AssetClassDomain, ModelDomain, ModelManufacturer) | 3 |
| Capabilities | 4 |
| Configurations | 6 |
| Detail virtual bases (abstract — no DB table) | 2 |
| Detail concrete: asset-level | 3 |
| Detail concrete: model-level | 2 |
| Detail template config tables | 3 |
| **Total concrete tables** | **28** |
