"""Technician live search — resolves any number (internal/NSN/legacy/MPN) to a Part."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.parts.presentation_layer.search.part_search import PartSearch


@require_http_methods(["GET"])
def part_search(request: HttpRequest) -> HttpResponse:
    term = request.GET.get("term", "").strip()
    results = [s.to_dict() for s in PartSearch.query(term)] if term else []
    fmt = request.GET.get("format", "")
    if fmt == "htmx-results":
        return render(request, "parts/_search_results.html", {"results": results, "term": term})
    return render(request, "parts/hub.html", {"results": results, "term": term})
