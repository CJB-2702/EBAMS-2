from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_not_required
def public_pricing(request: HttpRequest) -> HttpResponse:
    return render(request, "pub_pricing.html", {})
