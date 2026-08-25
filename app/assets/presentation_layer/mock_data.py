"""Mock data fallback for assets domain.

Single source of truth for all fixture shapes used by the mock entrypoints.
Mirrors the migrated models in ``app/assets/models/`` but uses plain dicts and
``SimpleNamespace`` graphs — **no ORM, no DB, no control layer**. Templates read
these objects with dot-access exactly as they will read real models later
(e.g. ``asset.model.model_name``, ``asset.domain.name``).

See ``assets_ui_plan_kit/mock_data_shapes.md`` for the documented shapes.
"""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

# ─────────────────────────────────────────────────────────────────────────────
# Fake audit identity
# ─────────────────────────────────────────────────────────────────────────────
FAKE_USER = SimpleNamespace(id=1, username="demo.tech", get_full_name=lambda: "Demo Tech")


def ns(**kwargs) -> SimpleNamespace:
    return SimpleNamespace(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Raw tables (dicts keyed/listed as in the DB)
# ─────────────────────────────────────────────────────────────────────────────
DOMAINS = [
    {"id": 1, "name": "North Fleet Ops"},
    {"id": 2, "name": "South Fleet Ops"},
    {"id": 3, "name": "Shared Engineering"},
]

MANUFACTURERS = [
    {"id": 1, "name": "Toyota", "code": "TYT", "website": "https://toyota.com", "is_active": True},
    {"id": 2, "name": "Caterpillar", "code": "CAT", "website": "https://cat.com", "is_active": True},
    {"id": 3, "name": "Hyster", "code": "HYS", "website": None, "is_active": True},
    {"id": 4, "name": "Genie", "code": "GEN", "website": "https://genielift.com", "is_active": False},
]

ASSET_CLASSES = [
    {"id": 1, "name": "Forklift", "category": "Material Handling",
     "description": "Powered industrial trucks for warehouse handling.",
     "is_active": True, "restrict_to_domain_set": False, "domains": [1, 2],
     "meter1_unit": "Hours", "meter2_unit": "Fuel", "meter3_unit": None, "meter4_unit": None},
    {"id": 2, "name": "Excavator", "category": "Heavy Equipment",
     "description": "Tracked hydraulic digging machines.",
     "is_active": True, "restrict_to_domain_set": True, "domains": [3],
     "meter1_unit": "Hours", "meter2_unit": "Fuel", "meter3_unit": None, "meter4_unit": None},
    {"id": 3, "name": "Boom Lift", "category": "Aerial",
     "description": "Self-propelled aerial work platforms.",
     "is_active": True, "restrict_to_domain_set": False, "domains": [1, 2, 3],
     "meter1_unit": "Hours", "meter2_unit": "Fuel", "meter3_unit": None, "meter4_unit": None},
]

ASSET_MODELS = [
    {"id": 1, "model_name": "8FGCU25", "version": "C", "version_rank": 1, "config_baselines": ["Cushion Tire", "Pneumatic Tire"],
     "is_base_model": True, "base_model": None, "asset_class": 1,
     "manufacturers": [1], "domains": [1, 2],
     "is_active": True},
    {"id": 2, "model_name": "320 GX", "version": "", "version_rank": None, "config_baselines": [],
     "is_base_model": True, "base_model": None, "asset_class": 2,
     "manufacturers": [2], "domains": [3],
     "is_active": True},
    {"id": 3, "model_name": "S60XL", "version": "B", "version_rank": 1, "config_baselines": ["Standard", "XL Cab"],
     "is_base_model": True, "base_model": None, "asset_class": 3,
     "manufacturers": [4], "domains": [1, 2, 3],
     "is_active": True},
    {"id": 4, "model_name": "8FGCU25", "version": "D", "version_rank": 2, "config_baselines": ["Cushion Tire"],
     "is_base_model": False, "base_model": 1, "asset_class": 1,
     "manufacturers": [1], "domains": [1, 2],
     "is_active": True},
]

ASSETS = [
    {"id": 1, "name": "FL-North-014", "serial_number": "8FG-2231-014",
     "status": "Active", "capability_status": "Operational", "is_active": True,
     "domain": 1, "model": 1, "asset_class": 1,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 4120.5, "meter2": 1880.0, "meter3": None, "meter4": None,
     "tags": ["lease", "north-dock"]},
    {"id": 2, "name": "FL-North-014-Mast", "serial_number": "8FG-2231-014-M",
     "status": "Active", "capability_status": "Limited", "is_active": True,
     "domain": 1, "model": 1, "asset_class": 1,
     "root_asset": 1, "parent_asset": 1, "depth_from_root": 1,
     "meter1": None, "meter2": None, "meter3": None, "meter4": None,
     "tags": []},
    {"id": 3, "name": "EX-Eng-002", "serial_number": "320GX-5567",
     "status": "Down", "capability_status": "Down", "is_active": True,
     "domain": 3, "model": 2, "asset_class": 2,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 980.0, "meter2": None, "meter3": None, "meter4": None,
     "tags": ["rental"]},
    {"id": 4, "name": "BL-South-007", "serial_number": "S60-9981",
     "status": "Active", "capability_status": "Operational", "is_active": True,
     "domain": 2, "model": 3, "asset_class": 3,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 612.0, "meter2": None, "meter3": None, "meter4": None,
     "tags": ["north-dock"]},
    {"id": 5, "name": "FL-South-021", "serial_number": "8FG-7742-021",
     "status": "Inactive", "capability_status": None, "is_active": False,
     "domain": 2, "model": 4, "asset_class": 1,
     "root_asset": None, "parent_asset": None, "depth_from_root": 0,
     "meter1": 15234.0, "meter2": 6021.0, "meter3": None, "meter4": None,
     "tags": ["retired"]},
]

ASSET_IMAGES = [
    {"id": 1, "asset": 1, "url": "https://placehold.co/640x380/2b3a55/ffffff?text=FL-014+front", "is_primary": True, "sort_order": 0},
    {"id": 2, "asset": 1, "url": "https://placehold.co/640x380/3a4a66/ffffff?text=FL-014+side", "is_primary": False, "sort_order": 1},
    {"id": 3, "asset": 1, "url": "https://placehold.co/640x380/4a5a77/ffffff?text=FL-014+data+plate", "is_primary": False, "sort_order": 2},
    {"id": 4, "asset": 4, "url": "https://placehold.co/640x380/55402b/ffffff?text=BL-007", "is_primary": True, "sort_order": 0},
]

METER_HISTORY = [
    {"id": 1, "asset": 1, "meter_index": 1, "value": 4120.5, "recorded_at": "2026-06-01 08:15", "source": "manual"},
    {"id": 2, "asset": 1, "meter_index": 1, "value": 4090.0, "recorded_at": "2026-05-20 07:50", "source": "telematics"},
    {"id": 3, "asset": 1, "meter_index": 2, "value": 1880.0, "recorded_at": "2026-06-01 08:15", "source": "manual"},
    {"id": 4, "asset": 3, "meter_index": 1, "value": 980.0, "recorded_at": "2026-05-30 16:02", "source": "telematics"},
    {"id": 5, "asset": 4, "meter_index": 1, "value": 612.0, "recorded_at": "2026-05-28 11:11", "source": "manual"},
]

# ── Capabilities (Phase 4) ──
CAPABILITY_DEFINITIONS = [
    {"id": 1, "name": "Lift 2500kg", "code": "LIFT2500", "description": "Rated lift capacity 2500kg.", "is_active": True},
    {"id": 2, "name": "Cold Storage Rated", "code": "COLD", "description": "Operates continuously at -20°C.", "is_active": True},
    {"id": 3, "name": "Indoor Emissions Safe", "code": "INDOOR", "description": "Electric / zero local emissions.", "is_active": True},
    {"id": 4, "name": "Reach 18m", "code": "REACH18", "description": "Working height up to 18 metres.", "is_active": False},
]
ASSET_CLASS_CAPABILITIES = [
    {"id": 1, "asset_class": 1, "capability_definition": 1, "is_active": True},
    {"id": 2, "asset_class": 3, "capability_definition": 4, "is_active": True},
]
MODEL_CAPABILITIES = [
    {"id": 1, "model": 1, "capability_definition": 1, "is_active": True},
    {"id": 2, "model": 1, "capability_definition": 3, "is_active": True},
]
ASSET_CAPABILITIES = [
    {"id": 1, "asset": 1, "capability_definition": 2, "is_active": True, "qty": 1, "notes": "Cold-cab retrofit kit."},
]

# ── Configurations (Phase 3) ──
# Each modification carries applicability (mirrors the real Phase-1 fields:
# applicability_mode + ModificationAssetClass / ModificationModel allow-lists).
# The four rows below exercise all four modes — see
# modification_applicability_ui_plan_kit/mock_data_shapes.md.
DEFINED_MODIFICATIONS = [
    {"id": 1, "name": "Side Shifter", "code": "SS01", "category": "Attachment",
     "description": "Hydraulic side shift carriage.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": [1]},
    {"id": 2, "name": "Cold Cab", "code": "CC01", "category": "Cab",
     "description": "Insulated heated operator cab.", "is_active": True,
     "applicability_mode": "model_set", "applicable_classes": [1], "applicable_models": [1, 4]},
    {"id": 3, "name": "LED Work Lights", "code": "LED1", "category": "Electrical",
     "description": "Front + rear LED light kit.", "is_active": True,
     "applicability_mode": "unrestricted", "applicable_classes": [], "applicable_models": []},
    {"id": 4, "name": "Engine Swap", "code": "ENG1", "category": "Powertrain",
     "description": "Heavy-duty engine replacement.", "is_active": True,
     "applicability_mode": "strict", "applicable_classes": [2], "applicable_models": [2]},
    {"id": 5, "name": "Fork Positioner", "code": "FP01", "category": "Attachment",
     "description": "Hydraulic fork positioner — adjusts tine spread without the operator dismounting.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": []},
    {"id": 6, "name": "Paper Roll Clamp", "code": "PRC1", "category": "Attachment",
     "description": "Single-double paper roll clamp rated to 1800 kg.", "is_active": True,
     "applicability_mode": "model_set", "applicable_classes": [], "applicable_models": [1, 4]},
    {"id": 7, "name": "Rotating Fork Attachment", "code": "RFA1", "category": "Attachment",
     "description": "360° rotating carriage for barrel and coil handling.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": []},
    {"id": 8, "name": "Blue Spot Safety Light", "code": "BSL1", "category": "Electrical",
     "description": "Floor-projected blue warning spot visible up to 8 m — pedestrian hazard alert.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": []},
    {"id": 9, "name": "Backup Alarm Upgrade", "code": "BAU1", "category": "Electrical",
     "description": "Broadband multi-frequency reverse alarm replacing factory unit.", "is_active": True,
     "applicability_mode": "unrestricted", "applicable_classes": [], "applicable_models": []},
    {"id": 10, "name": "Speed Limiter", "code": "SPL1", "category": "Electrical",
     "description": "Programmable zone-based speed restriction module — 4 km/h indoor cap.", "is_active": True,
     "applicability_mode": "unrestricted", "applicable_classes": [], "applicable_models": []},
    {"id": 11, "name": "Lithium Battery Conversion", "code": "LBC1", "category": "Powertrain",
     "description": "OEM lead-acid pack replaced with 48 V lithium iron phosphate — no topping-off required.", "is_active": True,
     "applicability_mode": "model_set", "applicable_classes": [], "applicable_models": [1, 4]},
    {"id": 12, "name": "Hydraulic Pump Upgrade", "code": "HPU1", "category": "Powertrain",
     "description": "High-flow pump kit — raises rated lift speed by 18%.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": []},
    {"id": 13, "name": "Overhead Guard Extension", "code": "OGE1", "category": "Cab",
     "description": "Extended overhead guard for racking aisles with low-clearance obstacles.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1], "applicable_models": []},
    {"id": 14, "name": "Seat Suspension Upgrade", "code": "SSU1", "category": "Cab",
     "description": "Air-ride suspension seat with lumbar support — reduces whole-body vibration.", "is_active": True,
     "applicability_mode": "unrestricted", "applicable_classes": [], "applicable_models": []},
    {"id": 15, "name": "Mirror Extension Kit", "code": "MEK1", "category": "Cab",
     "description": "Wide-angle convex mirror set — improves rear-quarter visibility in narrow aisles.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [1, 3], "applicable_models": []},
    {"id": 16, "name": "Strobe Warning Light", "code": "SWL1", "category": "Electrical",
     "description": "Amber LED strobe — 80-flash/min warning light for shared pedestrian zones.", "is_active": True,
     "applicability_mode": "unrestricted", "applicable_classes": [], "applicable_models": []},
    {"id": 17, "name": "Boom Angle Indicator", "code": "BAI1", "category": "Electrical",
     "description": "Digital inclinometer displaying live boom angle and safe working load.", "is_active": True,
     "applicability_mode": "strict", "applicable_classes": [3], "applicable_models": [3]},
    {"id": 18, "name": "Stabiliser Pad Set", "code": "SPS1", "category": "Attachment",
     "description": "Rubber-backed steel outrigger pads for soft or uneven ground.", "is_active": True,
     "applicability_mode": "class_only", "applicable_classes": [3], "applicable_models": []},
]
CONFIGURATION_TEMPLATES = [
    {"id": 1, "name": "Cold Storage Forklift", "revision": "A", "model": 1, "is_active": True,
     "description": "Standard build for refrigerated warehouses.",
     "modifications": [1, 2, 3],
     "children": [{"child_model": 1, "quantity": 1, "is_required": True}]},
    {"id": 2, "name": "Standard Yard Excavator", "revision": "A", "model": 2, "is_active": True,
     "description": "Baseline outdoor excavation build.",
     "modifications": [3], "children": []},
]
ASSET_CONFIGURATIONS = [
    {"id": 1, "asset": 1, "template": 1, "is_current": True, "verification_status": "partial",
     "documented_at": "2026-03-02 10:00", "notes": "Cold cab verified; side shifter pending inspection.",
     "actual_modifications": [
         {"defined_modification": 1, "applied_at": "2026-03-02", "is_active": True, "notes": "Bolt-on carriage."},
         {"defined_modification": 2, "applied_at": "2026-03-02", "is_active": True, "notes": ""},
     ]},
    {"id": 2, "asset": 5, "template": 1, "is_current": True, "verification_status": "verified",
     "documented_at": "2025-11-14 09:30", "notes": "Full inspection complete.",
     "actual_modifications": [
         {"defined_modification": 1, "applied_at": "2025-11-14", "is_active": True, "notes": ""},
         {"defined_modification": 2, "applied_at": "2025-11-14", "is_active": True, "notes": ""},
         {"defined_modification": 3, "applied_at": "2025-11-14", "is_active": True, "notes": ""},
     ]},
    {"id": 3, "asset": 3, "template": 2, "is_current": True, "verification_status": "verified",
     "documented_at": "2026-01-09 14:00", "notes": "",
     "actual_modifications": [
         {"defined_modification": 3, "applied_at": "2026-01-09", "is_active": True, "notes": ""},
     ]},
]


STATUS_CHOICES = ["Active", "Down", "Inactive"]
CAPABILITY_STATUS_CHOICES = ["Operational", "Limited", "Down"]


# ─────────────────────────────────────────────────────────────────────────────
# Lookups
# ─────────────────────────────────────────────────────────────────────────────
def _by_id(rows): return {r["id"]: r for r in rows}

_DOMAINS = _by_id(DOMAINS)
_MANUFACTURERS = _by_id(MANUFACTURERS)
_CLASSES = _by_id(ASSET_CLASSES)
_MODELS = _by_id(ASSET_MODELS)
_ASSETS = _by_id(ASSETS)
_CAPDEFS = _by_id(CAPABILITY_DEFINITIONS)
_MODS = _by_id(DEFINED_MODIFICATIONS)


def domain_ns(did):
    d = _DOMAINS.get(did)
    return ns(**d) if d else None


def manufacturer_ns(mid):
    m = _MANUFACTURERS.get(mid)
    return ns(**m) if m else None


def capdef_ns(cid):
    c = _CAPDEFS.get(cid)
    return ns(**c) if c else None


# ─────────────────────────────────────────────────────────────────────────────
# View-object builders (nested graphs)
# ─────────────────────────────────────────────────────────────────────────────
def _class_ns(cid, deep=False):
    c = _CLASSES.get(cid)
    if not c:
        return None
    obj = ns(**{k: v for k, v in c.items() if k != "domains"})
    obj.domains = [domain_ns(d) for d in c["domains"]]
    if deep:
        obj.capabilities = [
            ns(definition=capdef_ns(r["capability_definition"]), is_active=r["is_active"], source="class")
            for r in ASSET_CLASS_CAPABILITIES if r["asset_class"] == cid
        ]
        obj.model_count = sum(1 for m in ASSET_MODELS if m["asset_class"] == cid)
        obj.asset_count = sum(1 for a in ASSETS if a["asset_class"] == cid)
    return obj



def _model_ns(mid, deep=False):
    m = _MODELS.get(mid)
    if not m:
        return None
    obj = ns(**{k: v for k, v in m.items() if k not in ("manufacturers", "domains", "asset_class")})
    obj.asset_class = _class_ns(m["asset_class"])
    obj.manufacturers = [manufacturer_ns(x) for x in m["manufacturers"]]
    obj.domains = [domain_ns(d) for d in m["domains"]]
    obj.display_name = " ".join(
        p for p in [m["model_name"], m["version"]] if p
    )
    # Meter labels live on the class now — the model just reflects them.
    cls = _CLASSES.get(m["asset_class"], {})
    obj.meter_units = [
        u for u in [cls.get("meter1_unit"), cls.get("meter2_unit"),
                    cls.get("meter3_unit"), cls.get("meter4_unit")] if u
    ]
    if deep:
        obj.capabilities = [
            ns(definition=capdef_ns(r["capability_definition"]), is_active=r["is_active"], source="model")
            for r in MODEL_CAPABILITIES if r["model"] == mid
        ]
        obj.templates = [_template_ns(t["id"]) for t in CONFIGURATION_TEMPLATES if t["model"] == mid]
        obj.revisions = [_model_ns(r["id"]) for r in ASSET_MODELS if r["base_model"] == mid]
        obj.base = _model_ns(m["base_model"]) if m["base_model"] else None
        obj.asset_count = sum(1 for a in ASSETS if a["model"] == mid)
    return obj


def _manufacturer_ns(mid, deep=False):
    m = _MANUFACTURERS.get(mid)
    if not m:
        return None
    obj = ns(**m)
    if deep:
        obj.models = [_model_ns(am["id"]) for am in ASSET_MODELS if mid in am["manufacturers"]]
    return obj


def _meters(a):
    out = []
    cls = _CLASSES.get(a["asset_class"], {})
    for i in range(1, 5):
        val = a.get(f"meter{i}")
        if val is not None:
            out.append(ns(index=i, value=val, unit=cls.get(f"meter{i}_unit") or ""))
    return out


def _resolved_capabilities(a):
    """class ⊕ model ⊕ asset — merged display list (mock, not a real resolver)."""
    rows = []
    for r in ASSET_CLASS_CAPABILITIES:
        if r["asset_class"] == a["asset_class"]:
            rows.append(ns(definition=capdef_ns(r["capability_definition"]), source="Class",
                           is_active=r["is_active"], qty=None, notes=""))
    for r in MODEL_CAPABILITIES:
        if r["model"] == a["model"]:
            rows.append(ns(definition=capdef_ns(r["capability_definition"]), source="Model",
                           is_active=r["is_active"], qty=None, notes=""))
    for r in ASSET_CAPABILITIES:
        if r["asset"] == a["id"]:
            rows.append(ns(definition=capdef_ns(r["capability_definition"]), source="Asset",
                           is_active=r["is_active"], qty=r["qty"], notes=r["notes"]))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Applicability (Phase 1) — mirrors ApplicabilityPolicy / ApplicabilitySyncHandler.
# Pure helpers, no ORM. When the assets app goes real these swap 1:1 for the
# control layer (see modification_applicability_ui_plan_kit/mock_data_shapes.md).
# ─────────────────────────────────────────────────────────────────────────────
APPLICABILITY_MODES = ["unrestricted", "class_only", "model_set", "strict"]

MODE_META = {
    "unrestricted": ("Unrestricted", "is-light",
                     "Applies to any asset. Both lists are search hints only."),
    "class_only":   ("Class only", "is-info",
                     "Allowed when the asset's class is in the class list. Models are hints."),
    "model_set":    ("Model set", "is-link",
                     "Allowed when the asset's model is in the model list. Classes are auto-derived."),
    "strict":       ("Class + model", "is-warning",
                     "Allowed only when the asset's class AND model are both listed."),
}

# model_id -> parent class_id, for derivation + the dead-model guard.
MODEL_CLASS = {m["id"]: m["asset_class"] for m in ASSET_MODELS}

# A small fixed sample that surfaces every verdict (incl. the engine-mod-on-a-
# forklift case). Subset of ASSETS, flattened to what the policy needs.
PREVIEW_ASSETS = [
    {"id": 1, "name": "FL-North-014", "asset_class": 1, "model": 1},  # Forklift / 8FGCU25
    {"id": 3, "name": "EX-Eng-002",   "asset_class": 2, "model": 2},  # Excavator / 320 GX
    {"id": 5, "name": "FL-South-021", "asset_class": 1, "model": 4},  # Forklift / Rev D
]


def mock_derive_classes(model_ids):
    """Mirror ApplicabilitySyncHandler.sync_class_set: distinct parent classes."""
    return sorted({MODEL_CLASS[m] for m in model_ids if m in MODEL_CLASS})


def mock_is_allowed(mode, class_ids, model_ids, *, asset_class_id, asset_model_id):
    """Mirror ApplicabilityPolicy.is_allowed; returns (allowed, reason_or_None)."""
    class_ids, model_ids = set(class_ids), set(model_ids)
    if mode in ("strict", "class_only") and asset_class_id not in class_ids:
        return False, f"class not in permitted set {sorted(class_ids) or '{}'}"
    if mode in ("strict", "model_set") and asset_model_id not in model_ids:
        return False, f"model not in permitted set {sorted(model_ids) or '{}'}"
    return True, None


def _applicability_summary(mode, class_objs, model_objs):
    if mode == "unrestricted":
        return "Applies to any asset"
    if mode == "class_only":
        names = ", ".join(c.name for c in class_objs) or "no classes"
        return f"Class only · {names}"
    if mode == "model_set":
        return f"Model set · {len(model_objs)} model{'s' if len(model_objs) != 1 else ''}"
    return (f"Strict · {len(class_objs)} class{'es' if len(class_objs) != 1 else ''}"
            f" + {len(model_objs)} model{'s' if len(model_objs) != 1 else ''}")


def applicability_ns(mode, class_ids, model_ids):
    """Build the view object for one item's applicability (entity-agnostic)."""
    mode = mode or "unrestricted"
    derived = mode == "model_set"
    eff_class_ids = mock_derive_classes(model_ids) if derived else list(class_ids)
    class_objs = [c for c in (_class_ns(cid) for cid in eff_class_ids) if c]
    model_objs = [m for m in (_model_ns(mid) for mid in model_ids) if m]
    label, tag, helptext = MODE_META[mode]
    class_binding = mode in ("class_only", "strict")
    model_binding = mode in ("model_set", "strict")
    return ns(
        mode=mode, mode_label=label, mode_tag=tag, mode_help=helptext,
        class_ids=eff_class_ids, model_ids=list(model_ids),
        classes=class_objs, models=model_objs,
        class_binding=class_binding, model_binding=model_binding,
        class_derived=derived,
        summary=_applicability_summary(mode, class_objs, model_objs),
    )


def applicability_preview(mode, class_ids, model_ids):
    """Run the (mock) policy over PREVIEW_ASSETS → display rows."""
    rows = []
    eff_class_ids = mock_derive_classes(model_ids) if mode == "model_set" else list(class_ids)
    for a in PREVIEW_ASSETS:
        allowed, reason = mock_is_allowed(
            mode, eff_class_ids, model_ids,
            asset_class_id=a["asset_class"], asset_model_id=a["model"],
        )
        cls = _CLASSES.get(a["asset_class"], {})
        mdl = _MODELS.get(a["model"], {})
        rows.append(ns(id=a["id"], name=a["name"], allowed=allowed, reason=reason,
                       class_name=cls.get("name", "?"),
                       model_name=mdl.get("model_name", "?")))
    return rows


def preview_asset_rows():
    """PREVIEW_ASSETS flattened with display names — for the editor's live JS preview."""
    rows = []
    for a in PREVIEW_ASSETS:
        cls = _CLASSES.get(a["asset_class"], {})
        mdl = _MODELS.get(a["model"], {})
        rows.append({"id": a["id"], "name": a["name"],
                     "class_id": a["asset_class"], "model_id": a["model"],
                     "class_name": cls.get("name", "?"), "model_name": mdl.get("model_name", "?")})
    return rows


def get_asset_class_options():
    """Simple {id,name} list for the editor's class listbox."""
    return [ns(id=c["id"], name=c["name"]) for c in ASSET_CLASSES]


def get_asset_model_options():
    """Simple model options (with parent class) for the editor's model listbox."""
    return [ns(id=m["id"], label=_model_ns(m["id"]).display_name, asset_class=m["asset_class"])
            for m in ASSET_MODELS]


def _template_ns(tid):
    t = next((x for x in CONFIGURATION_TEMPLATES if x["id"] == tid), None)
    if not t:
        return None
    obj = ns(**{k: v for k, v in t.items() if k not in ("modifications", "children", "model")})
    obj.model = _model_ns(t["model"])
    obj.modifications = [ns(**_MODS[mid]) for mid in t["modifications"] if mid in _MODS]
    obj.children = [
        ns(child_model=_model_ns(c["child_model"]), quantity=c["quantity"], is_required=c["is_required"])
        for c in t["children"]
    ]
    return obj


def _asset_configuration_ns(asset_id):
    cfg = next((c for c in ASSET_CONFIGURATIONS if c["asset"] == asset_id and c["is_current"]), None)
    if not cfg:
        return None
    obj = ns(**{k: v for k, v in cfg.items() if k not in ("template", "actual_modifications")})
    obj.template = _template_ns(cfg["template"])
    obj.actual_modifications = [
        ns(modification=ns(**_MODS[am["defined_modification"]]), applied_at=am["applied_at"],
           is_active=am["is_active"], notes=am["notes"])
        for am in cfg["actual_modifications"]
    ]
    return obj



def _asset_ns(a, deep=False):
    obj = ns(**{k: v for k, v in a.items() if k not in ("domain", "model", "asset_class", "parent_asset", "root_asset")})
    obj.domain = domain_ns(a["domain"])
    obj.model = _model_ns(a["model"])
    obj.asset_class = _class_ns(a["asset_class"])
    obj.meters = _meters(a)
    obj.tags = a["tags"]
    if deep:
        obj.parent_asset = _asset_ns(_ASSETS[a["parent_asset"]]) if a["parent_asset"] else None
        obj.root_asset = _asset_ns(_ASSETS[a["root_asset"]]) if a["root_asset"] else None
        obj.children = [_asset_ns(c) for c in ASSETS if c["parent_asset"] == a["id"]]
        obj.images = sorted(
            [ns(**img) for img in ASSET_IMAGES if img["asset"] == a["id"]],
            key=lambda i: i.sort_order,
        )
        obj.primary_image = next((img for img in obj.images if img.is_primary), (obj.images[0] if obj.images else None))
        obj.capabilities = _resolved_capabilities(a)
        obj.configuration = _asset_configuration_ns(a["id"])
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Public accessors used by entrypoints
# ─────────────────────────────────────────────────────────────────────────────
def get_assets():
    return [_asset_ns(a) for a in ASSETS]


def get_asset(asset_id):
    a = _ASSETS.get(int(asset_id))
    return _asset_ns(a, deep=True) if a else None


def get_models():
    return [_model_ns(m["id"]) for m in ASSET_MODELS]


def get_model(model_id):
    return _model_ns(int(model_id), deep=True)


def get_classes():
    return [_class_ns(c["id"], deep=True) for c in ASSET_CLASSES]


def get_class(class_id):
    return _class_ns(int(class_id), deep=True)


def get_manufacturers():
    return [_manufacturer_ns(m["id"], deep=True) for m in MANUFACTURERS]


def get_manufacturer(mid):
    return _manufacturer_ns(int(mid), deep=True)


def get_meter_history():
    rows = []
    for r in METER_HISTORY:
        a = _ASSETS.get(r["asset"], {})
        cls = _CLASSES.get(a.get("asset_class"), {})
        unit = cls.get(f"meter{r['meter_index']}_unit") or ""
        rows.append(ns(asset=ns(id=a.get("id"), name=a.get("name")), meter_index=r["meter_index"],
                       value=r["value"], unit=unit, recorded_at=r["recorded_at"], source=r["source"]))
    return sorted(rows, key=lambda x: x.recorded_at, reverse=True)


def get_capability_definitions():
    out = []
    for c in CAPABILITY_DEFINITIONS:
        obj = ns(**c)
        obj.class_uses = sum(1 for r in ASSET_CLASS_CAPABILITIES if r["capability_definition"] == c["id"])
        obj.model_uses = sum(1 for r in MODEL_CAPABILITIES if r["capability_definition"] == c["id"])
        obj.asset_uses = sum(1 for r in ASSET_CAPABILITIES if r["capability_definition"] == c["id"])
        obj.assigned_class_ids = [r["asset_class"] for r in ASSET_CLASS_CAPABILITIES if r["capability_definition"] == c["id"]]
        obj.assigned_model_ids = [r["model"] for r in MODEL_CAPABILITIES if r["capability_definition"] == c["id"]]
        obj.assigned_asset_ids = [r["asset"] for r in ASSET_CAPABILITIES if r["capability_definition"] == c["id"]]
        out.append(obj)
    return out


def get_capability_definition(cid):
    return next((c for c in get_capability_definitions() if c.id == int(cid)), None)


def get_class_capability_rows():
    return [ns(id=r["id"], asset_class=_class_ns(r["asset_class"]), definition=capdef_ns(r["capability_definition"]),
               is_active=r["is_active"]) for r in ASSET_CLASS_CAPABILITIES]


def get_model_capability_rows():
    return [ns(id=r["id"], model=_model_ns(r["model"]), definition=capdef_ns(r["capability_definition"]),
               is_active=r["is_active"]) for r in MODEL_CAPABILITIES]


def get_asset_capability_rows():
    rows = []
    for r in ASSET_CAPABILITIES:
        a = _ASSETS.get(r["asset"], {})
        rows.append(ns(id=r["id"], asset=ns(id=a.get("id"), name=a.get("name")),
                       definition=capdef_ns(r["capability_definition"]), is_active=r["is_active"],
                       qty=r["qty"], notes=r["notes"]))
    return rows


def get_config_templates():
    return [_template_ns(t["id"]) for t in CONFIGURATION_TEMPLATES]


def get_config_template(tid):
    return _template_ns(int(tid))


def get_defined_modifications():
    out = []
    for m in DEFINED_MODIFICATIONS:
        obj = ns(**m)
        obj.template_uses = sum(1 for t in CONFIGURATION_TEMPLATES if m["id"] in t["modifications"])
        obj.applicability = applicability_ns(
            m.get("applicability_mode"), m.get("applicable_classes", []), m.get("applicable_models", []),
        )
        out.append(obj)
    return out


def get_defined_modification(mid):
    return next((m for m in get_defined_modifications() if m.id == int(mid)), None)


def count_template_asset_assignments(template_id: int) -> dict:
    tid = int(template_id)
    configs = [c for c in ASSET_CONFIGURATIONS if c["template"] == tid and c["is_current"]]
    return {
        "total": len(configs),
        "verified": sum(1 for c in configs if c["verification_status"] == "verified"),
        "partial": sum(1 for c in configs if c["verification_status"] == "partial"),
    }


def count_modification_asset_assignments(modification_id: int) -> int:
    mid = int(modification_id)
    return sum(
        1 for cfg in ASSET_CONFIGURATIONS
        if any(am["defined_modification"] == mid for am in cfg["actual_modifications"])
    )


def get_asset_configuration(asset_id):
    return _asset_configuration_ns(int(asset_id))


# ── Dashboard rollups ──
def dashboard_stats():
    active = [a for a in ASSETS if a["is_active"]]
    return ns(
        total_assets=len(ASSETS),
        active_assets=len(active),
        total_models=len(ASSET_MODELS),
        total_classes=len(ASSET_CLASSES),
        total_manufacturers=len(MANUFACTURERS),
        operational=sum(1 for a in ASSETS if a["capability_status"] == "Operational"),
        limited=sum(1 for a in ASSETS if a["capability_status"] == "Limited"),
        down=sum(1 for a in ASSETS if a["capability_status"] == "Down"),
        recent_assets=[_asset_ns(a) for a in ASSETS[:5]],
        by_domain=[
            ns(domain=ns(**d), count=sum(1 for a in ASSETS if a["domain"] == d["id"]))
            for d in DOMAINS
        ],
    )
