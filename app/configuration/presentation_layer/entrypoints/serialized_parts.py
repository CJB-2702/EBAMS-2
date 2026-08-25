"""Serialized part tracking (placeholder).

Empty landing pages for the future **serialized part tracking** feature set that
will live under the Configuration Management section — serial-numbered part
instances, the per-model templates that declare which serialized parts an asset
model is expected to carry, and the install/remove/transfer history for each one.

No models, control layer, or persistence is wired yet; these are intentional
stubs so the section's navigation is complete and demonstrable. See
``docs/assets/tech_debt/configuration_section_extraction.md`` for the build-out
plan and ``app/configuration/models/__init__.py`` for the planned model shapes.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def serialized_part_template_index(request: HttpRequest) -> HttpResponse:
    return render(request, "configuration/serialized_parts/templates.html")


@require_http_methods(["GET"])
def serialized_part_history_index(request: HttpRequest) -> HttpResponse:
    return render(request, "configuration/serialized_parts/history.html")
