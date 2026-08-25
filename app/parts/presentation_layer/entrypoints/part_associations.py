"""Part Associations (placeholder).

Empty landing pages for the future **association framework** that will live under the Parts
section — where Part definitions get associated to Asset Models and Asset Classes. No data or
control layer is wired yet; these are intentional stubs (see part_definitions_kit/).
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def part_model_association_index(request: HttpRequest) -> HttpResponse:
    return render(request, "parts/part_associations/model_associations.html")


@require_http_methods(["GET"])
def part_class_association_index(request: HttpRequest) -> HttpResponse:
    return render(request, "parts/part_associations/class_associations.html")
