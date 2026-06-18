"""Meter history list (mock)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.assets.presentation_layer import mock_data as mock


@require_http_methods(["GET"])
def meter_history_index(request: HttpRequest) -> HttpResponse:
    return render(request, "assets/meter_history/list.html", {"rows": mock.get_meter_history()})
