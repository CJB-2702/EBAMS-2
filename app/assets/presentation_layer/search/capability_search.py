"""Read helpers for the capability screens.

The capability pages span the definition catalog plus its class / model / asset
assignments and the resolved (cascaded) capability set per class/model/asset — well
past the inline read threshold — so every read lives here behind ``search/``.

Display helpers the templates expect but the schema does not carry (``display_name``
on a model, ``capabilities`` collections with cascade ``source``) are attached here
as plain attributes / ``SimpleNamespace`` rows, never on the models themselves.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.db.models import Count, QuerySet

from app.administration.models import Domain
from app.assets.models import (
    Asset,
    AssetClass,
    AssetClassCapability,
    AssetModel,
    CapabilityDefinition,
    Manufacturer,
    ModelCapability,
)
from app.assets.models.capabilities import AssetCapability

STATUS_CHOICES = ["Active", "Down", "Inactive"]


# ── small decorators ─────────────────────────────────────────────────────────

def _decorate_model(model: AssetModel) -> AssetModel:
    """Attach the ``display_name``/``base`` aliases the capability templates read."""
    model.display_name = str(model)
    model.base = model.base_model
    return model


def _capability_row(link, source: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=link.id,
        definition=link.capability_definition,
        is_active=link.is_active,
        source=source,
    )


# ── Definition catalog ───────────────────────────────────────────────────────

def search_capability_definitions() -> list[CapabilityDefinition]:
    """All definitions, each decorated with usage counts and assigned-id lists
    (the list page renders the ids into row data-attributes for client filtering)."""
    definitions = list(
        CapabilityDefinition.objects.prefetch_related(
            "asset_class_links", "model_links", "asset_links"
        ).order_by("name")
    )
    for d in definitions:
        class_ids = [link.asset_class_id for link in d.asset_class_links.all()]
        model_ids = [link.model_id for link in d.model_links.all()]
        asset_ids = [link.asset_id for link in d.asset_links.all()]
        d.assigned_class_ids = class_ids
        d.assigned_model_ids = model_ids
        d.assigned_asset_ids = asset_ids
        d.class_uses = len(class_ids)
        d.model_uses = len(model_ids)
        d.asset_uses = len(asset_ids)
    return definitions


def load_capability_definition_detail(definition_id: int) -> CapabilityDefinition | None:
    definition = CapabilityDefinition.objects.filter(id=definition_id).first()
    if definition is None:
        return None
    definition.class_uses = AssetClassCapability.objects.filter(
        capability_definition=definition
    ).count()
    definition.model_uses = ModelCapability.objects.filter(
        capability_definition=definition
    ).count()
    definition.asset_uses = AssetCapability.objects.filter(
        capability_definition=definition
    ).count()
    return definition


def _assigned_class_ids(definition_id: int) -> set[int]:
    return set(
        AssetClassCapability.objects.filter(
            capability_definition_id=definition_id
        ).values_list("asset_class_id", flat=True)
    )


def _assigned_model_ids(definition_id: int) -> set[int]:
    return set(
        ModelCapability.objects.filter(
            capability_definition_id=definition_id
        ).values_list("model_id", flat=True)
    )


def load_definition_assignment_editor(definition_id: int) -> dict:
    """Assigned/available classes and models for the definition edit screen."""
    assigned_class_ids = _assigned_class_ids(definition_id)
    assigned_model_ids = _assigned_model_ids(definition_id)

    all_classes = list(AssetClass.objects.order_by("name"))
    all_models = [
        _decorate_model(m)
        for m in AssetModel.objects.select_related("asset_class", "base_model")
        .prefetch_related("manufacturers")
        .order_by("model_name", "version")
    ]

    return {
        "assigned_classes": [c for c in all_classes if c.id in assigned_class_ids],
        "available_classes": [c for c in all_classes if c.id not in assigned_class_ids],
        "assigned_models": [m for m in all_models if m.id in assigned_model_ids],
        "available_models": [m for m in all_models if m.id not in assigned_model_ids],
    }


# ── By Class ─────────────────────────────────────────────────────────────────

def search_classes_with_capabilities(
    *,
    q: str = "",
    category: str = "",
    domain: str = "",
    definition: str = "",
    is_active: str = "",
) -> list[AssetClass]:
    qs = (
        AssetClass.objects.prefetch_related(
            "domains", "capability_links__capability_definition"
        )
        .annotate(
            model_count=Count("models", distinct=True),
            asset_count=Count("assets", distinct=True),
        )
        .order_by("name")
    )

    q = (q or "").strip()
    if q:
        qs = (qs.filter(name__icontains=q) | qs.filter(category__icontains=q)).distinct()
    if category:
        qs = qs.filter(category=category)
    if domain:
        qs = qs.filter(domains__id=domain).distinct()
    if is_active in ("True", "False"):
        qs = qs.filter(is_active=(is_active == "True"))

    classes = list(qs)
    for c in classes:
        c.capabilities = [
            _capability_row(link, "class") for link in c.capability_links.all()
        ]

    if definition:
        def_id = int(definition)
        classes = [
            c for c in classes
            if any(cap.definition.id == def_id for cap in c.capabilities)
        ]
    return classes


# ── By Model ─────────────────────────────────────────────────────────────────

def search_models_with_capabilities(
    *,
    q: str = "",
    asset_class: str = "",
    manufacturer: str = "",
    domain: str = "",
    is_base_model: str = "",
    definition: str = "",
    is_active: str = "",
) -> list[AssetModel]:
    qs = (
        AssetModel.objects.select_related("asset_class", "base_model")
        .prefetch_related(
            "manufacturers", "domains", "capability_links__capability_definition"
        )
        .annotate(asset_count=Count("assets", distinct=True))
        .order_by("model_name", "version")
    )

    q = (q or "").strip()
    if q:
        qs = (
            qs.filter(model_name__icontains=q)
            | qs.filter(version__icontains=q)
        ).distinct()
    if asset_class:
        qs = qs.filter(asset_class_id=asset_class)
    if manufacturer:
        qs = qs.filter(manufacturers__id=manufacturer).distinct()
    if domain:
        qs = qs.filter(domains__id=domain).distinct()
    if is_base_model in ("True", "False"):
        qs = qs.filter(is_base_model=(is_base_model == "True"))
    if is_active in ("True", "False"):
        qs = qs.filter(is_active=(is_active == "True"))

    models = list(qs)
    # Resolve the cascade: class-level capabilities + model-level capabilities.
    class_links: dict[int, list] = {}
    class_ids = {m.asset_class_id for m in models}
    for link in AssetClassCapability.objects.filter(
        asset_class_id__in=class_ids
    ).select_related("capability_definition"):
        class_links.setdefault(link.asset_class_id, []).append(link)

    for m in models:
        _decorate_model(m)
        m.class_capabilities = [
            _capability_row(link, "class")
            for link in class_links.get(m.asset_class_id, [])
        ]
        m.model_capabilities = [
            _capability_row(link, "model") for link in m.capability_links.all()
        ]
        m.all_capabilities = m.class_capabilities + m.model_capabilities

    if definition:
        def_id = int(definition)
        models = [
            m for m in models
            if any(cap.definition.id == def_id for cap in m.all_capabilities)
        ]
    return models


# ── By Asset ─────────────────────────────────────────────────────────────────

def _asset_source_label(provenance: str) -> str:
    return {"class": "Class", "model": "Model", "manual": "Asset"}.get(
        provenance, "Asset"
    )


def _attach_asset_capabilities(asset: Asset) -> Asset:
    """Attach a resolved ``.capabilities`` list with title-cased cascade source."""
    from app.assets.control_layer.domain_structs.asset_capability_struct import (
        AssetCapabilityStruct,
    )

    cap_struct = AssetCapabilityStruct.from_asset(asset)
    asset.capabilities = [
        SimpleNamespace(
            definition=ac.capability_definition,
            source=_asset_source_label(cap_struct.provenance_of(ac)),
            qty=ac.qty,
            notes=ac.notes,
            is_active=ac.is_active,
        )
        for ac in cap_struct.capabilities
    ]
    return asset


def search_assets_with_capabilities(
    *,
    q: str = "",
    domain: str = "",
    asset_class: str = "",
    model: str = "",
    manufacturer: str = "",
    status: str = "",
    capability_def_ids: list[int] | None = None,
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

    assets = [_attach_asset_capabilities(a) for a in qs]
    for a in assets:
        a.model.display_name = str(a.model)

    if capability_def_ids:
        required = set(capability_def_ids)
        assets = [
            a for a in assets
            if required.issubset({cap.definition.id for cap in a.capabilities})
        ]
    return assets


def load_asset_capabilities_detail(asset_id: int) -> Asset | None:
    asset = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .filter(id=asset_id)
        .first()
    )
    if asset is None:
        return None
    asset.model.display_name = str(asset.model)
    return _attach_asset_capabilities(asset)


def load_asset_capabilities_editor(asset_id: int) -> dict | None:
    """Available definitions, editable manual rows, and read-only inherited rows."""
    from app.assets.control_layer.domain_structs.asset_capability_struct import (
        AssetCapabilityStruct,
    )

    asset = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .filter(id=asset_id)
        .first()
    )
    if asset is None:
        return None
    asset.model.display_name = str(asset.model)

    cap_struct = AssetCapabilityStruct.from_asset(asset, active_only=False)

    assigned: list[SimpleNamespace] = []
    inherited: list[SimpleNamespace] = []
    assigned_def_ids: set[int] = set()
    for ac in cap_struct.capabilities:
        provenance = cap_struct.provenance_of(ac)
        assigned_def_ids.add(ac.capability_definition_id)
        if provenance == "manual":
            assigned.append(
                SimpleNamespace(
                    definition=ac.capability_definition,
                    qty=ac.qty,
                    notes=ac.notes or "",
                    is_active=ac.is_active,
                )
            )
        else:
            inherited.append(
                SimpleNamespace(
                    definition=ac.capability_definition,
                    source=_asset_source_label(provenance),
                )
            )

    available = [
        d
        for d in CapabilityDefinition.objects.filter(is_active=True).order_by("name")
        if d.id not in assigned_def_ids
    ]

    return {
        "asset": asset,
        "capabilities_available": available,
        "capabilities_assigned": assigned,
        "capabilities_inherited": inherited,
    }


# ── Asset bulk management (one definition × many assets) ─────────────────────

def load_asset_bulk_management(definition_id: int) -> dict:
    assigned_rows = {
        ac.asset_id: ac
        for ac in AssetCapability.objects.filter(capability_definition_id=definition_id)
    }
    assigned_class_ids = _assigned_class_ids(definition_id)
    assigned_model_ids = _assigned_model_ids(definition_id)

    all_classes = list(AssetClass.objects.order_by("name"))
    all_models = [
        _decorate_model(m)
        for m in AssetModel.objects.select_related("asset_class")
        .prefetch_related("manufacturers")
        .order_by("model_name", "version")
    ]

    assigned_assets: list[Asset] = []
    available_assets: list[Asset] = []
    for asset in (
        Asset.objects.select_related("asset_class", "model").order_by("name")
    ):
        asset.model.display_name = str(asset.model)
        row = assigned_rows.get(asset.id)
        if row is not None:
            asset.assignment_qty = row.qty or 1
            asset.assignment_notes = row.notes or ""
            asset.assignment_is_active = row.is_active
            assigned_assets.append(asset)
        else:
            available_assets.append(asset)

    return {
        "assigned_assets": assigned_assets,
        "available_assets": available_assets,
        "assigned_classes": [c for c in all_classes if c.id in assigned_class_ids],
        "assigned_models": [m for m in all_models if m.id in assigned_model_ids],
        "all_classes": all_classes,
        "all_models": all_models,
    }


# ── Reference lists shared by several pages ──────────────────────────────────

def reference_lists() -> dict:
    return {
        "all_classes": list(AssetClass.objects.order_by("name")),
        "all_models": [
            _decorate_model(m)
            for m in AssetModel.objects.select_related("asset_class").order_by(
                "model_name", "version"
            )
        ],
        "all_manufacturers": list(Manufacturer.objects.order_by("name")),
        "all_domains": list(Domain.objects.order_by("name")),
        "all_assets": list(Asset.objects.order_by("name")),
        "all_categories": list(
            AssetClass.objects.exclude(category__isnull=True)
            .exclude(category="")
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        ),
    }
