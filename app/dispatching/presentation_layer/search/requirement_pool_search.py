"""Read helpers for the template requirement-manifest editor's picker
panels — capabilities and material (parts). Models and modifications reuse
assets' own `model_index` / `defined_modification_index` htmx-search-results
branches directly (dispatching_starter_kit/build_phase_3_ui.md §1.2); those
two do not, so dispatching carries small ones of its own, same as the skills
picker already does."""

from __future__ import annotations

from django.db.models import QuerySet

from app.assets.models import CapabilityDefinition, ConfigurationTemplate
from app.parts.models import Part


def search_capability_definitions(*, q: str = "") -> QuerySet[CapabilityDefinition]:
    qs = CapabilityDefinition.objects.filter(is_active=True).order_by("name")
    q = (q or "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    return qs


def search_configuration_templates(*, q: str = "", model_id: int | None = None) -> QuerySet[ConfigurationTemplate]:
    qs = ConfigurationTemplate.objects.filter(is_active=True).select_related("model").order_by("name")
    if model_id:
        qs = qs.filter(model_id=model_id)
    q = (q or "").strip()
    if q:
        qs = qs.filter(name__icontains=q)
    return qs


def search_parts_for_material_requirement(*, q: str = "") -> QuerySet[Part]:
    qs = Part.objects.filter(is_active=True).order_by("part_number")
    q = (q or "").strip()
    if q:
        qs = qs.filter(part_number__icontains=q) | qs.filter(name__icontains=q)
    return qs
