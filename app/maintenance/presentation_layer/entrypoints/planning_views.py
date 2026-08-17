"""Recurring maintenance plans — calendar-based scheduling only in this build.
Meter-based plans are recognized by the model but MaintenancePlanner does not
evaluate them yet (see MaintenancePlanner.plan_for docstring); the UI reflects
that by labelling meter plans "not yet evaluated" rather than pretending they
run.

Legacy: presentation/routes/maintenance/planning/.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.models.core.asset_class import AssetClass
from app.maintenance.control_layer.planning.maintenance_plan_context import (
    MaintenancePlanContext,
)
from app.maintenance.control_layer.planning.maintenance_planner import (
    MaintenancePlanner,
)
from app.maintenance.models.planning.maintenance_plan import (
    MaintenancePlan,
    PlanFrequencyType,
    PlanStatus,
)
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)


@require_http_methods(["GET"])
def plan_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    status = request.GET.get("status", "").strip()
    qs = MaintenancePlan.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).select_related("domain", "asset_class", "asset_model", "template_action_set")
    if status:
        qs = qs.filter(status=status)
    plans = qs.order_by("name")
    return render(
        request,
        "maintenance/planning/index.html",
        {"plans": plans, "status": status, "statuses": PlanStatus.choices},
    )


@require_http_methods(["GET", "POST"])
def plan_detail(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(
        MaintenancePlan.objects.select_related(
            "domain", "asset_class", "asset_model", "template_action_set"
        ),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, plan.domain_id):
        raise Http404

    ctx = MaintenancePlanContext(pk)

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "activate":
            ctx.activate(actor=request.user)
            messages.success(request, "Plan activated.")
        elif action == "deactivate":
            ctx.deactivate(actor=request.user)
            messages.success(request, "Plan deactivated.")
        elif action == "run":
            results = MaintenancePlanner.plan_for(plan)
            created = MaintenancePlanner.create_events_from_results(results, actor=request.user)
            if created:
                messages.success(request, f"{len(created)} maintenance event(s) generated.")
            else:
                messages.success(request, "No assets are currently due under this plan.")
        else:
            messages.error(request, "Unknown action.")
        return redirect(reverse("plan_detail", kwargs={"pk": pk}))

    preview = (
        MaintenancePlanner.plan_for(plan)
        if plan.status == PlanStatus.ACTIVE
        else []
    )
    return render(
        request,
        "maintenance/planning/detail.html",
        {"plan": plan, "preview": preview},
    )


@require_http_methods(["GET", "POST"])
def plan_create(request: HttpRequest) -> HttpResponse:
    user_domain_ids = list(request.user.get_all_domain_ids())

    if request.method == "POST":
        domain_id_raw = request.POST.get("domain_id", "").strip()
        domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None
        if domain_id not in user_domain_ids:
            messages.error(request, "You may only create a plan in a domain you are assigned to.")
            return redirect(reverse("plan_create"))

        name = request.POST.get("name", "").strip()
        template_id_raw = request.POST.get("template_action_set_id", "").strip()
        asset_class_id_raw = request.POST.get("asset_class_id", "").strip()
        if not name or not template_id_raw.isdigit() or not asset_class_id_raw.isdigit():
            messages.error(request, "Name, template, and asset class are required.")
            return redirect(reverse("plan_create"))

        frequency_type = request.POST.get("frequency_type", PlanFrequencyType.CALENDAR)
        delta_days_raw = request.POST.get("delta_days", "").strip()
        plan = MaintenancePlan.objects.create(
            name=name,
            description=request.POST.get("description", ""),
            status=PlanStatus.ACTIVE,
            domain_id=domain_id,
            asset_class_id=int(asset_class_id_raw),
            asset_model_id=(
                int(request.POST["asset_model_id"])
                if request.POST.get("asset_model_id", "").strip().isdigit()
                else None
            ),
            template_action_set_id=int(template_id_raw),
            frequency_type=frequency_type,
            delta_days=float(delta_days_raw) if delta_days_raw else None,
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Plan '{plan.name}' created.")
        return redirect(reverse("plan_detail", kwargs={"pk": plan.pk}))

    domains = Domain.objects.filter(pk__in=user_domain_ids).order_by("name")
    templates = TemplateActionSet.objects.filter(
        domain_id__in=user_domain_ids, deleted_at__isnull=True, is_active=True
    ).order_by("task_name")
    asset_classes = AssetClass.objects.all().order_by("name")
    return render(
        request,
        "maintenance/planning/create.html",
        {
            "domains": domains,
            "show_domain_picker": domains.count() > 1,
            "single_domain": domains.first() if domains.count() == 1 else None,
            "templates": templates,
            "asset_classes": asset_classes,
            "frequency_types": PlanFrequencyType.choices,
        },
    )
