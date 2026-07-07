"""Read helpers for asset-model list / detail screens.

The model screens span class, manufacturers, domains, revisions, capabilities and
an asset count — far past the inline threshold — so reads live here behind
``search/``. ``load_model_detail`` attaches a ``meter_units`` convenience list the
detail template iterates (kept off the model, which holds schema only).
"""

from __future__ import annotations

from django.db.models import Count, QuerySet

from app.assets.models import AssetModel


def search_models(
    *,
    q: str = "",
    asset_class: str = "",
    manufacturer: str = "",
    domain: str = "",
    is_base_model: str = "",
) -> QuerySet[AssetModel]:
    qs = (
        AssetModel.objects.select_related("asset_class", "base_model")
        .prefetch_related("manufacturers", "domains")
        .annotate(asset_count=Count("assets", distinct=True))
        .order_by("model_name", "subtype_name")
    )

    q = (q or "").strip()
    if q:
        qs = (
            qs.filter(model_name__icontains=q)
            | qs.filter(subtype_name__icontains=q)
            | qs.filter(revision__icontains=q)
        )
        qs = qs.distinct()
    if asset_class:
        qs = qs.filter(asset_class_id=asset_class)
    if manufacturer:
        qs = qs.filter(manufacturers__id=manufacturer)
    if domain:
        qs = qs.filter(domains__id=domain)
    if is_base_model in ("True", "False"):
        qs = qs.filter(is_base_model=(is_base_model == "True"))

    return qs


def load_model_detail(model_id: int) -> AssetModel | None:
    model = (
        AssetModel.objects.select_related("asset_class", "base_model")
        .prefetch_related(
            "manufacturers",
            "domains",
            "revisions",
            "configuration_templates",
            "capability_links__capability_definition",
        )
        .annotate(asset_count=Count("assets", distinct=True))
        .filter(id=model_id)
        .first()
    )
    if model is not None:
        model.meter_units = [
            u
            for u in (
                model.meter1_unit,
                model.meter2_unit,
                model.meter3_unit,
                model.meter4_unit,
            )
            if u
        ]
    return model
