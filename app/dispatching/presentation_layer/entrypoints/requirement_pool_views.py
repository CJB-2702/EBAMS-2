"""HTMX search fragments backing the template draft editor's requirement
picker panels. Capabilities and material (parts) get small fragments of
their own here, same shape as skill_search's; models and modifications reuse
assets' own model_index / defined_modification_index htmx-search-results
branches directly rather than duplicating them (build_phase_3_ui.md §1.2)."""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods

from app.dispatching.presentation_layer.search.requirement_pool_search import (
    search_capability_definitions,
    search_configuration_templates,
    search_parts_for_material_requirement,
)
from app.dispatching.presentation_layer.tools.dispatching_access import can_author_templates


@require_http_methods(["GET"])
def capability_pool_search(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied
    q = request.GET.get("q", "").strip()
    results = [
        f'<li data-value="{c.pk}">{c.name}</li>' for c in search_capability_definitions(q=q)
    ]
    if not results:
        return HttpResponse('<li class="is-disabled">No matches.</li>')
    return HttpResponse("\n".join(results))


@require_http_methods(["GET"])
def configuration_template_pool_search(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied
    q = request.GET.get("q", "").strip()
    model_id_raw = request.GET.get("model_id", "").strip()
    if not model_id_raw.isdigit():
        return HttpResponse('<li class="is-disabled">Pick a model first.</li>')
    results = [
        f'<li data-value="{c.pk}">{c.name}{f" (rev {c.revision})" if c.revision else ""}</li>'
        for c in search_configuration_templates(q=q, model_id=int(model_id_raw))
    ]
    if not results:
        return HttpResponse('<li class="is-disabled">No matches.</li>')
    return HttpResponse("\n".join(results))


@require_http_methods(["GET"])
def material_pool_search(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied
    q = request.GET.get("q", "").strip()
    results = [
        f'<li data-value="{p.pk}">[{p.part_number}] {p.name}</li>'
        for p in search_parts_for_material_requirement(q=q)
    ]
    if not results:
        return HttpResponse('<li class="is-disabled">No matches.</li>')
    return HttpResponse("\n".join(results))
