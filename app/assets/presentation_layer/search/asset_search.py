"""Read helpers for the asset screens.

The asset list and 360 detail span many tables (class, model, manufacturers,
domain, meters, images, capabilities, configuration, hierarchy), so all reads live
here behind ``search/``. The detail loader returns the asset plus the computed
display bundles the 360 template needs (meters/images/capabilities/configuration)
as separate values — the reverse relations ``images``/``children`` can't be
shadowed on the instance, so the view passes these alongside ``asset``.
"""

from __future__ import annotations

from types import SimpleNamespace

from django.db.models import QuerySet

from app.assets.control_layer.domain_structs.asset_capability_struct import (
    AssetCapabilityStruct,
)
from app.assets.control_layer.domain_structs.asset_configuration_struct import (
    AssetConfigurationStruct,
)
from app.assets.models import Asset
from app.events.models import Attachment
from app.events.presentation_layer.tools.generic_cards import document_dict


def search_assets(
    *,
    q: str = "",
    domain: str = "",
    asset_class: str = "",
    model: str = "",
    manufacturer: str = "",
    status: str = "",
    capability_status: str = "",
    config_baseline: str = "",
) -> QuerySet[Asset]:
    qs = (
        Asset.objects.select_related("asset_class", "model", "domain")
        .prefetch_related("model__manufacturers")
        .order_by("name")
    )

    q = (q or "").strip()
    if q:
        matches = (
            qs.filter(name__icontains=q)
            | qs.filter(serial_number__icontains=q)
            | qs.filter(config_baseline__icontains=q)
            # One box, both ways of naming an asset. A user hunting for a
            # specific unit types its id or its model name with equal
            # expectation of a hit, and making them pick the right field
            # first is the kind of friction that gets a filter ignored.
            | qs.filter(model__model_name__icontains=q)
        )
        if q.isdigit():
            matches = matches | qs.filter(id=int(q))
        qs = matches.distinct()
    if config_baseline:
        qs = qs.filter(config_baseline__icontains=config_baseline)
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
    if capability_status:
        qs = qs.filter(capability_status=capability_status)

    return qs


def load_asset_base(asset_id: int) -> Asset | None:
    """The asset with header FK slices for edit/hierarchy/meter screens."""
    return (
        Asset.objects.select_related(
            "asset_class", "model", "domain", "parent_asset", "root_asset"
        )
        .prefetch_related("children")
        .filter(id=asset_id)
        .first()
    )


def build_meter_rows(asset: Asset) -> list[SimpleNamespace]:
    """Current meters as ``(index, unit, value)`` for indices the asset's class
    defines a unit for. Labels live on AssetClass (every model under a class
    shares the same meter semantics); the reading values stay on Asset."""
    asset_class = asset.asset_class
    units = [
        asset_class.meter1_unit, asset_class.meter2_unit,
        asset_class.meter3_unit, asset_class.meter4_unit,
    ]
    values = [asset.meter1, asset.meter2, asset.meter3, asset.meter4]
    rows: list[SimpleNamespace] = []
    for index, (unit, value) in enumerate(zip(units, values), start=1):
        if unit:
            rows.append(SimpleNamespace(index=index, unit=unit, value=value))
    return rows


def load_meter_history(asset: Asset) -> list[SimpleNamespace]:
    """Meter-history rows for an asset, each annotated with its class's unit."""
    asset_class = asset.asset_class
    units = {
        1: asset_class.meter1_unit,
        2: asset_class.meter2_unit,
        3: asset_class.meter3_unit,
        4: asset_class.meter4_unit,
    }
    rows = []
    for r in asset.meter_history.all():
        rows.append(
            SimpleNamespace(
                recorded_at=r.recorded_at,
                meter_index=r.meter_index,
                value=r.value,
                unit=units.get(r.meter_index) or "",
                source=r.source or "manual",
            )
        )
    return rows


def load_asset_detail(asset_id: int) -> dict | None:
    """The 360 detail bundle: the asset plus computed display collections."""
    asset = (
        Asset.objects.select_related(
            "asset_class", "model", "domain", "parent_asset", "root_asset",
            "primary_image__file",
        )
        .prefetch_related("children")
        .filter(id=asset_id)
        .first()
    )
    if asset is None:
        return None

    cap_struct = AssetCapabilityStruct.from_asset(asset)
    capabilities = [
        SimpleNamespace(
            definition=ac.capability_definition,
            source=cap_struct.provenance_of(ac),
            qty=ac.qty,
            notes=ac.notes,
        )
        for ac in cap_struct.capabilities
    ]

    cfg_struct = AssetConfigurationStruct.from_asset(asset)
    if cfg_struct.asset_configuration is not None:
        configuration = SimpleNamespace(
            template=cfg_struct.asset_configuration.template,
            verification_status=cfg_struct.asset_configuration.verification_status,
            actual_modifications=[
                SimpleNamespace(modification=am.defined_modification)
                for am in cfg_struct.actual_modifications
            ],
        )
    else:
        configuration = None

    image_rows = list(
        Attachment.objects.active()
        .filter(thread_id=asset.photo_gallery_id)
        .select_related("file")
    )
    primary_image = asset.primary_image
    if primary_image is None and image_rows:
        primary_image = image_rows[0]

    return {
        "asset": asset,
        "meters": build_meter_rows(asset),
        "capabilities": capabilities,
        "configuration": configuration,
        "images": image_rows,
        "image_documents": [document_dict(a) for a in image_rows],
        "primary_image": primary_image,
    }
