"""Proto action library — reusable standalone action steps a Planner can drop
into a template draft or directly onto a live event.

Legacy: presentation/routes/maintenance/proto_action_portal.py.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
)


@require_http_methods(["GET"])
def proto_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    q = request.GET.get("q", "").strip()
    qs = ProtoActionItem.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).select_related("domain")
    if q:
        qs = qs.filter(action_name__icontains=q)
    items = qs.order_by("action_name")
    context = {"items": items, "q": q}
    if request.GET.get("format") == "htmx-search-results":
        return render(request, "maintenance/proto/_index_results.html", context)
    return render(request, "maintenance/proto/index.html", context)


@require_http_methods(["GET", "POST"])
def proto_create(request: HttpRequest) -> HttpResponse:
    """Simple single-card form — ProtoActionItem's tool/part-demand children
    are added from its detail page after creation, matching TemplateActionItem's
    own shape but without the wizard weight since a proto item is a tiny,
    single-purpose library row."""
    user_domain_ids = list(request.user.get_all_domain_ids())

    if request.method == "POST":
        domain_id_raw = request.POST.get("domain_id", "").strip()
        domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None
        if domain_id not in user_domain_ids:
            messages.error(request, "You may only create a library item in a domain you are assigned to.")
            return redirect(reverse("proto_create"))

        action_name = request.POST.get("action_name", "").strip()
        if not action_name:
            messages.error(request, "Action name is required.")
            return redirect(reverse("proto_create"))

        duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
        item = ProtoActionItem.objects.create(
            domain_id=domain_id,
            action_name=action_name,
            description=request.POST.get("description", ""),
            instructions=request.POST.get("instructions", ""),
            safety_notes=request.POST.get("safety_notes", ""),
            notes=request.POST.get("notes", ""),
            estimated_duration_minutes=int(duration_raw) if duration_raw.isdigit() else None,
            minimum_staff_count=int(request.POST.get("minimum_staff_count", 1) or 1),
            required_skills=request.POST.get("required_skills", ""),
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Library action '{item.action_name}' created.")
        return redirect(reverse("proto_index"))

    domains = Domain.objects.filter(pk__in=user_domain_ids).order_by("name")
    return render(
        request,
        "maintenance/proto/create.html",
        {
            "domains": domains,
            "show_domain_picker": domains.count() > 1,
            "single_domain": domains.first() if domains.count() == 1 else None,
        },
    )
