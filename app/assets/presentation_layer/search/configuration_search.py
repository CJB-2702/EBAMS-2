"""Read helpers for the configuration screens.

Covers the defined-modification catalog, the applicability authoring surface, the
configuration-template builder/detail, and the per-asset configuration screens.
Every page spans several tables (modification + allow-lists, template + links +
children, asset + config + actual modifications), so all reads live here.

The view-shaping the templates expect but the schema does not carry — an
``applicability`` view object with mode labels / binding flags / resolved class &
model objects, ``display_name`` on models, ``configuration`` bundles on assets — is
built here as plain attributes / ``SimpleNamespace`` rows, never on the models.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.db.models import Count

from app.administration.models import Domain
from app.assets.control_layer.configurations.applicability.applicability_policy import (
    ApplicabilityPolicy,
)
from app.assets.control_layer.configurations.applicability.applicability_struct import (
    ApplicabilityStruct,
)
from app.assets.control_layer.domain_structs.configuration_template_struct import (
    ConfigurationTemplateStruct,
)
from app.assets.models import (
    Asset,
    AssetClass,
    AssetModel,
    ConfigurationTemplate,
    DefinedModification,
    Manufacturer,
)
from app.assets.models.configurations import (
    ActualModification,
    AssetConfiguration,
    ApplicabilityMode,
    TemplateModification,
    VerificationStatus,
)

STATUS_CHOICES = ["Active", "Down", "Inactive"]
APPLICABILITY_MODES = ["unrestricted", "class_only", "model_set", "strict"]

MODE_META = {
    "unrestricted": ("Unrestricted", "is-light",
                     "Applies to any asset. Both lists are search hints only."),
    "class_only": ("Class only", "is-info",
                   "Allowed when the asset's class is in the class list. Models are hints."),
    "model_set": ("Model set", "is-link",
                  "Allowed when the asset's model is in the model list. Classes are auto-derived."),
    "strict": ("Class + model", "is-warning",
               "Allowed only when the asset's class AND model are both listed."),
}


# ── small helpers ────────────────────────────────────────────────────────────

def _decorate_model(model: AssetModel) -> AssetModel:
    model.display_name = str(model)
    return model


def _derive_class_ids(model_ids: list[int]) -> list[int]:
    if not model_ids:
        return []
    return sorted(
        set(
            AssetModel.objects.filter(id__in=model_ids).values_list(
                "asset_class_id", flat=True
            )
        )
    )


def _applicability_summary(mode, class_objs, model_objs) -> str:
    if mode == "unrestricted":
        return "Applies to any asset"
    if mode == "class_only":
        names = ", ".join(c.name for c in class_objs) or "no classes"
        return f"Class only · {names}"
    if mode == "model_set":
        n = len(model_objs)
        return f"Model set · {n} model{'s' if n != 1 else ''}"
    return (
        f"Strict · {len(class_objs)} class{'es' if len(class_objs) != 1 else ''}"
        f" + {len(model_objs)} model{'s' if len(model_objs) != 1 else ''}"
    )


def applicability_view(defined_mod: DefinedModification, mode: str | None = None):
    """Entity-view of one modification's applicability (mirrors the runtime struct).

    ``mode`` may override the stored mode (the editor reshapes panels per the
    selected mode without persisting it yet).
    """
    raw_class_ids = list(
        defined_mod.class_allowlist.values_list("asset_class_id", flat=True)
    )
    raw_model_ids = list(
        defined_mod.model_allowlist.values_list("model_id", flat=True)
    )
    mode = mode or defined_mod.applicability_mode
    derived = mode == "model_set"
    eff_class_ids = _derive_class_ids(raw_model_ids) if derived else raw_class_ids

    class_objs = list(AssetClass.objects.filter(id__in=eff_class_ids).order_by("name"))
    model_objs = [
        _decorate_model(m)
        for m in AssetModel.objects.filter(id__in=raw_model_ids)
        .select_related("asset_class")
        .order_by("model_name", "subtype_name")
    ]
    label, tag, helptext = MODE_META.get(mode, MODE_META["unrestricted"])

    return SimpleNamespace(
        mode=mode,
        mode_label=label,
        mode_tag=tag,
        mode_help=helptext,
        class_ids=eff_class_ids,
        model_ids=raw_model_ids,
        classes=class_objs,
        models=model_objs,
        class_objs=class_objs,
        model_objs=model_objs,
        class_binding=mode in ("class_only", "strict"),
        model_binding=mode in ("model_set", "strict"),
        class_derived=derived,
        summary=_applicability_summary(mode, class_objs, model_objs),
    )


def _modification_struct(defined_mod: DefinedModification) -> ApplicabilityStruct:
    return ApplicabilityStruct(
        mode=ApplicabilityMode(defined_mod.applicability_mode),
        class_ids=frozenset(
            defined_mod.class_allowlist.values_list("asset_class_id", flat=True)
        ),
        model_ids=frozenset(
            defined_mod.model_allowlist.values_list("model_id", flat=True)
        ),
    )


def _asset_allowed(defined_mod: DefinedModification, asset: Asset) -> tuple[bool, str | None]:
    struct = _modification_struct(defined_mod)
    allowed = ApplicabilityPolicy.is_allowed(
        struct, asset_class_id=asset.asset_class_id, asset_model_id=asset.model_id
    )
    reason = None if allowed else ApplicabilityPolicy.explain(
        struct, asset_class_id=asset.asset_class_id, asset_model_id=asset.model_id
    )
    return allowed, reason


# ── Configurations hub ───────────────────────────────────────────────────────

def index_counts() -> dict:
    return {
        "templates_count": ConfigurationTemplate.objects.count(),
        "modifications_count": DefinedModification.objects.count(),
        "assets_count": Asset.objects.count(),
    }


# ── Defined modifications ────────────────────────────────────────────────────

def search_defined_modifications() -> list[DefinedModification]:
    mods = list(
        DefinedModification.objects.prefetch_related(
            "class_allowlist", "model_allowlist"
        )
        .annotate(template_uses=Count("template_links", distinct=True))
        .order_by("name")
    )
    for m in mods:
        m.applicability = applicability_view(m)
    return mods


def modification_categories() -> list[str]:
    return sorted(
        DefinedModification.objects.exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
    )


def load_defined_modification_detail(modification_id: int):
    mod = (
        DefinedModification.objects.annotate(
            template_uses=Count("template_links", distinct=True)
        )
        .filter(id=modification_id)
        .first()
    )
    if mod is None:
        return None
    mod.applicability = applicability_view(mod)
    asset_count = ActualModification.objects.filter(
        defined_modification=mod, is_active=True
    ).count()
    return mod, asset_count


def load_applicability_editor(modification_id: int, mode: str | None = None) -> dict | None:
    mod = DefinedModification.objects.filter(id=modification_id).first()
    if mod is None:
        return None
    if mode not in APPLICABILITY_MODES:
        mode = mod.applicability_mode

    view = applicability_view(mod, mode)
    selected_class_ids = set(view.class_ids)
    selected_model_ids = set(view.model_ids)

    class_options = list(AssetClass.objects.order_by("name"))
    model_options = [
        SimpleNamespace(id=m.id, label=str(m), asset_class=m.asset_class_id)
        for m in AssetModel.objects.select_related("asset_class").order_by(
            "model_name", "subtype_name"
        )
    ]

    preview_assets, preview = _applicability_preview(view)

    return {
        "modification": mod,
        "mode": mode,
        "applicability": view,
        "classes_selected": [c for c in class_options if c.id in selected_class_ids],
        "classes_available": [c for c in class_options if c.id not in selected_class_ids],
        "models_selected": [m for m in model_options if m.id in selected_model_ids],
        "models_available": [m for m in model_options if m.id not in selected_model_ids],
        "model_class_map": {m.id: m.asset_class for m in model_options},
        "preview_assets": preview_assets,
        "preview": preview,
        "mode_choices": [(v, MODE_META[v][0]) for v in APPLICABILITY_MODES],
    }


def _applicability_preview(view) -> tuple[list[dict], list[SimpleNamespace]]:
    struct = ApplicabilityStruct(
        mode=ApplicabilityMode(view.mode),
        class_ids=frozenset(view.class_ids),
        model_ids=frozenset(view.model_ids),
    )
    sample = list(
        Asset.objects.select_related("asset_class", "model").order_by("name")[:12]
    )
    json_rows: list[dict] = []
    preview_rows: list[SimpleNamespace] = []
    for a in sample:
        allowed = ApplicabilityPolicy.is_allowed(
            struct, asset_class_id=a.asset_class_id, asset_model_id=a.model_id
        )
        reason = None if allowed else ApplicabilityPolicy.explain(
            struct, asset_class_id=a.asset_class_id, asset_model_id=a.model_id
        )
        json_rows.append({
            "id": a.id, "name": a.name,
            "class_id": a.asset_class_id, "model_id": a.model_id,
            "class_name": a.asset_class.name, "model_name": str(a.model),
        })
        preview_rows.append(SimpleNamespace(
            id=a.id, name=a.name, allowed=allowed, reason=reason,
            class_name=a.asset_class.name, model_name=str(a.model),
        ))
    return json_rows, preview_rows


# ── Configuration templates ──────────────────────────────────────────────────

def _decorate_template(template: ConfigurationTemplate) -> ConfigurationTemplate:
    _decorate_model(template.model)
    template.code = template.revision or ""
    template.modifications = [
        link.defined_modification for link in template.modification_links.all()
    ]
    children = list(template.child_declarations.all())
    for child in children:
        _decorate_model(child.child_model)
    template.children = children
    return template


def _template_queryset():
    return ConfigurationTemplate.objects.select_related("model").prefetch_related(
        "modification_links__defined_modification",
        "child_declarations__child_model",
    )


def search_config_templates(
    *, q: str = "", model_id: str = "", modification_id: str = ""
) -> list[ConfigurationTemplate]:
    qs = _template_queryset().order_by("name")
    q = (q or "").strip()
    if q:
        qs = (qs.filter(name__icontains=q) | qs.filter(description__icontains=q)).distinct()
    if model_id:
        qs = qs.filter(model_id=model_id)
    if modification_id:
        qs = qs.filter(modification_links__defined_modification_id=modification_id).distinct()
    return [_decorate_template(t) for t in qs]


def load_config_template_detail(template_id: int):
    template = _template_queryset().filter(id=template_id).first()
    if template is None:
        return None
    _decorate_template(template)
    configs = AssetConfiguration.objects.filter(template=template)
    asset_stats = {
        "total": configs.values("asset_id").distinct().count(),
        "verified": configs.filter(
            verification_status=VerificationStatus.COMPLETE
        ).count(),
        "partial": configs.filter(
            verification_status=VerificationStatus.PARTIAL
        ).count(),
    }
    return template, asset_stats


def load_config_template_editor(template_id: int) -> dict | None:
    template = _template_queryset().filter(id=template_id).first()
    if template is None:
        return None
    _decorate_template(template)
    selected_ids = {m.id for m in template.modifications}
    all_mods = list(DefinedModification.objects.order_by("name"))
    # Pool of models assignable as expected children — every model except the
    # template's own target model (a template can't declare its own model as child).
    child_models = [
        _decorate_model(m)
        for m in AssetModel.objects.select_related("asset_class")
        .exclude(id=template.model_id)
        .order_by("model_name", "subtype_name")
    ]
    return {
        "template": template,
        "models": [_decorate_model(m) for m in AssetModel.objects.order_by("model_name")],
        "modifications_available": [m for m in all_mods if m.id not in selected_ids],
        "modifications_selected": [m for m in all_mods if m.id in selected_ids],
        "child_models": child_models,
        "child_classes": list(AssetClass.objects.order_by("name")),
        "initial_children": [
            {
                "model_id": ch.child_model_id,
                "name": ch.child_model.display_name,
                "quantity": ch.quantity,
                "is_required": ch.is_required,
                "child_configuration": ch.child_configuration or "",
            }
            for ch in template.children
        ],
    }


def template_filter_labels(model_id: str, modification_id: str) -> dict:
    selected_model = None
    if model_id:
        m = AssetModel.objects.filter(id=model_id).first()
        if m:
            selected_model = _decorate_model(m)
    selected_modification = (
        DefinedModification.objects.filter(id=modification_id).first()
        if modification_id else None
    )
    return {
        "selected_model": selected_model,
        "selected_modification": selected_modification,
    }


def asset_filter_labels(asset_class_id: str, model_id: str) -> dict:
    """Resolve display labels for the by-asset search-dropdown filters so a
    selected asset class / model survives a full-page reload."""
    selected_class = (
        AssetClass.objects.filter(id=asset_class_id).first()
        if asset_class_id else None
    )
    selected_model = None
    if model_id:
        m = AssetModel.objects.filter(id=model_id).first()
        if m:
            selected_model = _decorate_model(m)
    return {
        "selected_class": selected_class,
        "selected_model": selected_model,
    }


# ── Per-asset configuration ──────────────────────────────────────────────────

def _build_configuration_view(asset: Asset):
    """Bundle the asset's current config + its active actual modifications.

    Returns None when the asset has no configuration. Actual modifications belong
    to the asset (not the config row), so they are gathered here and attached.
    """
    config = (
        AssetConfiguration.objects.select_related("template", "template__model")
        .filter(asset=asset)
        .order_by("-created_at")
        .first()
    )
    actual = [
        SimpleNamespace(
            modification=am.defined_modification,
            applied_at=am.applied_at,
            notes=am.notes,
            is_active=am.is_active,
        )
        for am in ActualModification.objects.filter(asset=asset, is_active=True)
        .select_related("defined_modification")
        .order_by("defined_modification__name")
    ]
    if config is None:
        # by_asset reads ``asset.configuration.template`` even when absent.
        return SimpleNamespace(template=None, actual_modifications=actual) if actual else \
            SimpleNamespace(template=None, actual_modifications=[])
    config.actual_modifications = actual
    if config.template is not None:
        config.template.code = config.template.revision or ""
        _decorate_model(config.template.model)
    return config


def load_asset_children_configurations(asset: Asset) -> list[SimpleNamespace]:
    """One layer deep: each DIRECT child of ``asset`` with its current configuration
    template, verification status, and active modification count. Does not recurse —
    grandchildren are not included."""
    children = list(
        Asset.objects.filter(parent_asset=asset)
        .select_related("asset_class", "model")
        .order_by("name")
    )
    if not children:
        return []

    child_ids = [c.id for c in children]

    # Newest configuration per child (rows are left in place; "latest wins").
    latest_by_asset: dict[int, AssetConfiguration] = {}
    for cfg in (
        AssetConfiguration.objects.filter(asset_id__in=child_ids)
        .select_related("template")
        .order_by("asset_id", "-created_at")
    ):
        latest_by_asset.setdefault(cfg.asset_id, cfg)

    mod_counts = {
        row["asset_id"]: row["n"]
        for row in (
            ActualModification.objects.filter(asset_id__in=child_ids, is_active=True)
            .values("asset_id")
            .annotate(n=Count("id"))
        )
    }

    rows: list[SimpleNamespace] = []
    for child in children:
        cfg = latest_by_asset.get(child.id)
        rows.append(SimpleNamespace(
            asset=child,
            template=cfg.template if cfg else None,
            verification_status=cfg.verification_status if cfg else None,
            modification_count=mod_counts.get(child.id, 0),
        ))
    return rows


def load_asset_configuration_detail(asset_id: int):
    asset = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .filter(id=asset_id)
        .first()
    )
    if asset is None:
        return None
    _decorate_model(asset.model)
    # Always return the configuration view so the status and actual-modifications
    # cards render even when no template is assigned. Expected-side data is only
    # available when a template is present.
    configuration = _build_configuration_view(asset)
    configuration.expected_modifications = []
    configuration.expected_children = []
    if configuration.template is not None:
        # Expected-side, straight from the template: modifications + child models.
        expected = ConfigurationTemplateStruct.from_template(configuration.template)
        configuration.expected_modifications = expected.modifications
        configuration.expected_children = expected.children
    children_configurations = load_asset_children_configurations(asset)
    return asset, configuration, children_configurations


def search_assets_with_configuration(
    *,
    q: str = "",
    domain: str = "",
    asset_class: str = "",
    model: str = "",
    manufacturer: str = "",
    status: str = "",
    template_id: str = "",
) -> list[Asset]:
    qs = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .prefetch_related("model__manufacturers")
        .order_by("name")
    )
    q = (q or "").strip()
    if q:
        qs = (qs.filter(name__icontains=q) | qs.filter(serial_number__icontains=q)).distinct()
    if domain:
        qs = qs.filter(domain_id=domain)
    if asset_class:
        qs = qs.filter(asset_class_id=asset_class)
    if model:
        qs = qs.filter(model_id=model)
    if manufacturer:
        qs = qs.filter(model__manufacturers__id=manufacturer).distinct()
    if status:
        qs = qs.filter(status=status)

    assets = list(qs)
    for a in assets:
        _decorate_model(a.model)
        a.configuration = _build_configuration_view(a)

    if template_id:
        tid = int(template_id)
        assets = [
            a for a in assets
            if a.configuration.template is not None
            and a.configuration.template.id == tid
        ]
    return assets


def load_asset_configuration_editor(asset_id: int) -> dict | None:
    asset = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .filter(id=asset_id)
        .first()
    )
    if asset is None:
        return None
    _decorate_model(asset.model)
    configuration = _build_configuration_view(asset)
    if configuration.template is not None:
        configuration.template.modifications = [
            link.defined_modification
            for link in configuration.template.modification_links.all()
        ]

    assigned_ids = set(
        ActualModification.objects.filter(asset=asset, is_active=True).values_list(
            "defined_modification_id", flat=True
        )
    )
    all_mods = list(
        DefinedModification.objects.filter(is_active=True)
        .prefetch_related("class_allowlist", "model_allowlist")
        .order_by("name")
    )
    modifications_assigned = [m for m in all_mods if m.id in assigned_ids]
    modifications_available = []
    for m in all_mods:
        if m.id in assigned_ids:
            continue
        m.applicability = applicability_view(m)
        allowed, reason = _asset_allowed(m, asset)
        m.allowed = allowed
        m.block_reason = reason or ""
        modifications_available.append(m)

    return {
        "asset": asset,
        "configuration": configuration if configuration.template is not None else None,
        "templates": list(
            ConfigurationTemplate.objects.filter(
                model=asset.model, is_active=True
            ).order_by("name")
        ),
        "modifications_available": modifications_available,
        "modifications_assigned": modifications_assigned,
        "asset_class_options": list(AssetClass.objects.order_by("name")),
        "model_options": [
            SimpleNamespace(id=m.id, label=str(m), asset_class=m.asset_class_id)
            for m in AssetModel.objects.select_related("asset_class").order_by("model_name")
        ],
    }


# ── Reference lists shared by several pages ──────────────────────────────────

def reference_lists() -> dict:
    return {
        "classes": list(AssetClass.objects.order_by("name")),
        "models": [_decorate_model(m) for m in AssetModel.objects.order_by("model_name")],
        "manufacturers": list(Manufacturer.objects.order_by("name")),
        "domains": list(Domain.objects.order_by("name")),
        "templates": [_decorate_template_lite(t) for t in _template_queryset().order_by("name")],
    }


def _decorate_template_lite(template: ConfigurationTemplate) -> ConfigurationTemplate:
    template.code = template.revision or ""
    return template
