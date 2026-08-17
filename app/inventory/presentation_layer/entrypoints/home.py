"""The Inventory app landing page — cards for each sub-area. Later phases
(Intake, Movements, Issues, Audits) fill in hrefs and empty states as they
land; the cards render now regardless (rule 5), each honestly "Not built
yet" until then.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def inventory_home(request: HttpRequest) -> HttpResponse:
    return render(request, "inventory/home.html", {})
