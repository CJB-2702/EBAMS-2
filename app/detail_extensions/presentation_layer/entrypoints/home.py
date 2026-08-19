from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def home_landing(request: HttpRequest) -> HttpResponse:
    """Landing page for the detail extensions app explaining how they trigger on create

    and detailing policy configuration instructions.
    """
    return render(request, "detail_extensions/home.html")


@require_http_methods(["GET"])
def serial_number_templates(request: HttpRequest) -> HttpResponse:
    """Placeholder view for Asset Serial Number Templates and Tracking."""
    return render(request, "detail_extensions/serial_number_templates.html")
