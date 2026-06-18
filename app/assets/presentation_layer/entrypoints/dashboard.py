"""Assets dashboard (mock)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def asset_dashboard(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/dashboard.html", {"stats": mock.dashboard_stats()})
