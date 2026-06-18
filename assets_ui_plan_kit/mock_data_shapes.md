# Mock Data Shapes

The hard-coded fixtures that feed the mock. These mirror the **new** model
fields in [`app/assets/models/`](../app/assets/models/). They live in a single
module (proposed: `app/assets/presentation_layer/mock_data.py`) as plain dicts /
lists, imported by entrypoints. **No ORM, no DB.**

Audit fields (`created_at`, `updated_at`, `created_by`, `updated_by`) are mocked
with a single fake user dict where a template needs to show them.

## Core entities

```python
DOMAINS = [                       # administration.Domain (access scope)
    {"id": 1, "name": "North Fleet Ops"},
    {"id": 2, "name": "South Fleet Ops"},
    {"id": 3, "name": "Shared Engineering"},
]

MANUFACTURERS = [                 # Manufacturer  (NEW — split from MakeModel.make)
    {"id": 1, "name": "Toyota", "code": "TYT", "website": "https://toyota.com", "is_active": True},
    {"id": 2, "name": "Caterpillar", "code": "CAT", "website": "https://cat.com", "is_active": True},
    {"id": 3, "name": "Hyster", "code": "HYS", "website": None, "is_active": True},
]

ASSET_CLASSES = [                 # AssetClass  (old "Asset Type")
    {"id": 1, "name": "Forklift", "category": "Material Handling",
     "description": "Powered industrial trucks", "is_active": True,
     "restrict_to_domain_set": False, "domains": [1, 2]},
    {"id": 2, "name": "Excavator", "category": "Heavy Equipment",
     "description": "Tracked digging machines", "is_active": True,
     "restrict_to_domain_set": True, "domains": [3]},
]

ASSET_MODELS = [                  # AssetModel  (old MakeModel)
    {"id": 1, "model_name": "8FGCU25", "subtype_name": "Cushion Tire",
     "revision": "C", "is_base_model": True, "base_model": None,
     "asset_class": 1, "manufacturers": [1], "domains": [1, 2],
     "meter1_unit": "Hours", "meter2_unit": "Miles",
     "meter3_unit": None, "meter4_unit": None, "is_active": True,
     "plugins_provisioned": ["purchase_info", "vehicle_registration"]},
    {"id": 2, "model_name": "320 GX", "subtype_name": None,
     "revision": None, "is_base_model": True, "base_model": None,
     "asset_class": 2, "manufacturers": [2], "domains": [3],
     "meter1_unit": "Hours", "meter2_unit": None,
     "meter3_unit": None, "meter4_unit": None, "is_active": True,
     "plugins_provisioned": ["purchase_info"]},
]

ASSETS = [                        # Asset
    {"id": 1, "name": "FL-North-014", "serial_number": "8FG-2231-014",
     "status": "Active", "capability_status": "Operational", "is_active": True,
     "domain": 1, "model": 1, "asset_class": 1,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 4120.5, "meter2": 1880.0, "meter3": None, "meter4": None,
     "tags": ["lease", "north-dock"],
     "plugins_provisioned": ["purchase_info", "vehicle_registration"]},
    {"id": 2, "name": "FL-North-014-Mast", "serial_number": "8FG-2231-014-M",
     "status": "Active", "capability_status": "Limited", "is_active": True,
     "domain": 1, "model": 1, "asset_class": 1,
     "root_asset": 1, "parent_asset": 1, "depth_from_root": 1,
     "meter1": None, "meter2": None, "meter3": None, "meter4": None,
     "tags": [], "plugins_provisioned": []},
    {"id": 3, "name": "EX-Eng-002", "serial_number": "320GX-5567",
     "status": "Down", "capability_status": "Down", "is_active": True,
     "domain": 3, "model": 2, "asset_class": 2,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 980.0, "meter2": None, "meter3": None, "meter4": None,
     "tags": ["rental"], "plugins_provisioned": ["purchase_info"]},
]

ASSET_IMAGES = [                  # AssetImage  (carousel)
    {"id": 1, "asset": 1, "url": "https://placehold.co/640x360?text=FL-014",
     "is_primary": True, "sort_order": 0},
    {"id": 2, "asset": 1, "url": "https://placehold.co/640x360?text=FL-014+side",
     "is_primary": False, "sort_order": 1},
]

METER_HISTORY = [                 # MeterHistory
    {"id": 1, "asset": 1, "meter_index": 1, "value": 4120.5,
     "recorded_at": "2026-06-01 08:15", "source": "manual"},
    {"id": 2, "asset": 1, "meter_index": 1, "value": 4090.0,
     "recorded_at": "2026-05-20 07:50", "source": "telematics"},
]
```

## Capabilities *(Phase 4)*

```python
CAPABILITY_DEFINITIONS = [        # CapabilityDefinition
    {"id": 1, "name": "Lift 2500kg", "code": "LIFT2500",
     "description": "Rated lift capacity 2500kg", "is_active": True},
    {"id": 2, "name": "Cold Storage Rated", "code": "COLD",
     "description": "Operates at -20C", "is_active": True},
]
ASSET_CLASS_CAPABILITIES = [{"id": 1, "asset_class": 1, "capability_definition": 1, "is_active": True}]
MODEL_CAPABILITIES       = [{"id": 1, "model": 1, "capability_definition": 1, "is_active": True}]
ASSET_CAPABILITIES       = [{"id": 1, "asset": 1, "capability_definition": 2,
                             "is_active": True, "qty": 1, "notes": "Retrofit kit"}]
```

The Asset-360 "Capabilities (resolved)" card composes class ⊕ model ⊕ asset rows
in the mock — a hard-coded merged list, not a real resolver.

## Configurations *(Phase 3)*

```python
DEFINED_MODIFICATIONS = [         # DefinedModification
    {"id": 1, "name": "Side Shifter", "code": "SS01",
     "category": "Attachment", "is_active": True},
    {"id": 2, "name": "Cold Cab", "code": "CC01",
     "category": "Cab", "is_active": True},
]
CONFIGURATION_TEMPLATES = [       # ConfigurationTemplate (+ children/mods)
    {"id": 1, "name": "Cold Storage Forklift", "revision": "A",
     "model": 1, "is_active": True,
     "modifications": [1, 2],
     "children": [{"child_model": 1, "quantity": 1, "is_required": True}]},
]
ASSET_CONFIGURATIONS = [          # AssetConfiguration + ActualModification
    {"id": 1, "asset": 1, "template": 1, "is_current": True,
     "verification_status": "partial",
     "actual_modifications": [
         {"defined_modification": 1, "applied_at": "2026-03-02", "is_active": True},
     ]},
]
```

## Plugins *(Phase 2 — illustrative)*

Each plugin owns its own typed table; in the mock each is just a dict keyed by
asset id. Two first-party samples ported from the old detail tables:

```python
PLUGIN_REGISTRY = [               # the framework's enabled-plugin list
    {"key": "purchase_info", "label": "Purchase Info", "icon": "receipt_long",
     "target": "asset", "cardinality": "one-to-one"},
    {"key": "vehicle_registration", "label": "Vehicle Registration", "icon": "badge",
     "target": "asset", "cardinality": "one-to-one"},
]
PLUGIN_DATA = {
    "purchase_info": {1: {"po_number": "PO-88123", "vendor": "ACME Lift Co",
                          "purchase_date": "2024-11-10", "cost": "32,400.00"}},
    "vehicle_registration": {1: {"plate": "FK-1142", "state": "TX",
                                 "expires": "2027-01-31"}},
}
```

## Status → tag colour map (UI helper)

| `status` / `capability_status` | Bulma tag |
| :--- | :--- |
| Active / Operational | `is-success` |
| Limited | `is-warning` |
| Down / Inactive | `is-danger` |
| (other) | `is-light` |
</content>
