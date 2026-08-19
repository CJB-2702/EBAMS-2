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
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.assets.models.core.asset_class import AssetClass
from app.assets.models import AssetModel
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
from app.maintenance.presentation_layer.search.template_model_search import models_for_class


@require_http_methods(["GET"])
def plan_index(request: HttpRequest) -> HttpResponse:
    domain_ids = accessible_domain_ids(request)
    
    name_q = request.GET.get("name", "").strip()
    asset_class_id = request.GET.get("asset_class_id", "").strip()
    model_id = request.GET.get("model_id", "").strip()
    status = request.GET.get("status", "").strip()
    frequency_type = request.GET.get("frequency_type", "").strip()

    qs = MaintenancePlan.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).select_related("domain", "asset_class", "template_action_set").prefetch_related("asset_models")

    if name_q:
        qs = qs.filter(name__icontains=name_q)
    if asset_class_id.isdigit():
        qs = qs.filter(asset_class_id=int(asset_class_id))
    if model_id.isdigit():
        qs = qs.filter(asset_models__id=int(model_id))
    if status:
        qs = qs.filter(status=status)
    if frequency_type:
        qs = qs.filter(frequency_type=frequency_type)

    plans = qs.order_by("name")
    
    current_filters = {
        "name": name_q,
        "asset_class_id": int(asset_class_id) if asset_class_id.isdigit() else "",
        "model_id": int(model_id) if model_id.isdigit() else "",
        "status": status,
        "frequency_type": frequency_type,
    }

    return render(
        request,
        "maintenance/planning/index.html",
        {
            "plans": plans,
            "asset_classes": AssetClass.objects.all().order_by("name"),
            "make_models": AssetModel.objects.all().order_by("model_name"),
            "statuses": PlanStatus.choices,
            "frequency_types": PlanFrequencyType.choices,
            "current_filters": current_filters,
        },
    )


@require_http_methods(["GET", "POST"])
def plan_detail(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(
        MaintenancePlan.objects.select_related(
            "domain", "asset_class", "template_action_set"
        ).prefetch_related("asset_models"),
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
        elif action == "delete":
            plan.deleted_at = timezone.now() if hasattr(timezone, "now") else None
            # Fallback if timezone not imported
            from django.utils import timezone as django_tz
            plan.deleted_at = django_tz.now()
            plan.updated_by = request.user
            plan.save()
            messages.success(request, f"Plan '{plan.name}' deleted.")
            return redirect(reverse("plan_index"))
        else:
            messages.error(request, "Unknown action.")
        return redirect(reverse("plan_detail", kwargs={"pk": pk}))

    preview = (
        MaintenancePlanner.plan_for(plan)
        if plan.status == PlanStatus.ACTIVE
        else []
    )
    template = plan.template_action_set
    template_items = (
        list(
            template.template_action_items.filter(deleted_at__isnull=True).order_by(
                "sequence_order"
            )
        )
        if template
        else []
    )

    return render(
        request,
        "maintenance/planning/detail.html",
        {
            "plan": plan,
            "preview": preview,
            "template": template,
            "template_items": template_items,
            "comments_card": ActivityThreadManager(plan, thread_attr="activity_thread").card(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def plan_create(request: HttpRequest) -> HttpResponse:
    user_domain_ids = list(request.user.get_all_domain_ids())

    if request.method == "GET":
        fmt = request.GET.get("format", "")
        if fmt == "htmx-models":
            asset_class_id = request.GET.get("asset_class_id", "").strip()
            models = []
            if asset_class_id.isdigit():
                models = models_for_class(int(asset_class_id))
            return render(
                request,
                "maintenance/planning/_models_options.html",
                {"models": models},
            )
        elif fmt == "htmx-templates":
            return _template_results(request)

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
        
        plan = MaintenancePlan.objects.create(
            name=name,
            description=request.POST.get("description", ""),
            status=PlanStatus.ACTIVE,
            domain_id=domain_id,
            asset_class_id=int(asset_class_id_raw),
            template_action_set_id=int(template_id_raw),
            frequency_type=frequency_type,
            created_by=request.user,
            updated_by=request.user,
        )

        for field in ("delta_days", "delta_m1", "delta_m2", "delta_m3", "delta_m4"):
            raw = request.POST.get(field, "").strip()
            setattr(plan, field, float(raw) if raw else None)
        plan.save()

        # Handle Many-to-Many models
        model_ids = [
            int(v) for v in request.POST.getlist("asset_model_ids") if v.strip().isdigit()
        ]
        if model_ids:
            valid_models = AssetModel.objects.filter(asset_class_id=plan.asset_class_id, pk__in=model_ids)
            plan.asset_models.set(valid_models)

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


@require_http_methods(["GET", "POST"])
def plan_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """The create form, pre-populated (legacy /maintenance-plan/<id>/edit)."""
    plan = get_object_or_404(
        MaintenancePlan.objects.select_related(
            "domain", "asset_class", "template_action_set"
        ).prefetch_related("asset_models"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, plan.domain_id):
        raise Http404

    if request.method == "GET" and request.GET.get("format") == "htmx-templates":
        return _template_results(request)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Plan name is required.")
            return redirect(reverse("plan_edit", kwargs={"pk": pk}))

        plan.name = name
        plan.description = request.POST.get("description", "")
        plan.status = request.POST.get("status", plan.status)
        plan.frequency_type = request.POST.get("frequency_type", plan.frequency_type)

        asset_class_id = request.POST.get("asset_class_id", "").strip()
        if asset_class_id.isdigit():
            # If changing asset class, clear existing assigned models because they don't apply anymore
            new_class_id = int(asset_class_id)
            if plan.asset_class_id != new_class_id:
                plan.asset_class_id = new_class_id
                plan.asset_models.clear()

        template_id = request.POST.get("template_action_set_id", "").strip()
        if template_id.isdigit():
            plan.template_action_set_id = int(template_id)

        for field in ("delta_days", "delta_m1", "delta_m2", "delta_m3", "delta_m4"):
            raw = request.POST.get(field, "").strip()
            setattr(plan, field, float(raw) if raw else None)

        plan.updated_by = request.user
        plan.save()
        messages.success(request, "Plan updated.")
        return redirect(reverse("plan_detail", kwargs={"pk": pk}))

    domain_ids = accessible_domain_ids(request)
    assigned_models = list(plan.asset_models.all())
    assigned_model_ids = {m.pk for m in assigned_models}
    models_available = [
        m for m in models_for_class(plan.asset_class_id) if m.pk not in assigned_model_ids
    ]

    return render(
        request,
        "maintenance/planning/edit.html",
        {
            "plan": plan,
            "asset_classes": AssetClass.objects.all().order_by("name"),
            "templates": TemplateActionSet.objects.filter(
                domain_id__in=domain_ids, deleted_at__isnull=True, is_active=True
            ).order_by("task_name"),
            "statuses": PlanStatus.choices,
            "frequency_types": PlanFrequencyType.choices,
            "models_available": models_available,
            "models_assigned": assigned_models,
        },
    )


@require_http_methods(["POST"])
def plan_move_asset_models(request: HttpRequest, pk: int) -> HttpResponse:
    """Dual-listbox move endpoint for the plan's model tags (HTMX-only)."""
    plan = get_object_or_404(
        MaintenancePlan.objects.select_related("asset_class"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, plan.domain_id):
        raise Http404

    ids = [
        int(v) for v in request.POST.getlist("asset_model_ids") if str(v).strip().isdigit()
    ]
    direction = request.POST.get("direction", "add")
    if not ids:
        return HttpResponse("Select at least one model.", status=400)

    if direction == "add":
        valid_models = AssetModel.objects.filter(asset_class_id=plan.asset_class_id, pk__in=ids)
        plan.asset_models.add(*valid_models)
        msg = "Models added to plan."
    else:
        plan.asset_models.remove(*ids)
        msg = "Models removed from plan."

    plan.updated_by = request.user
    plan.save()

    assigned_models = list(plan.asset_models.all())
    assigned_model_ids = {m.pk for m in assigned_models}
    models_available = [
        m for m in models_for_class(plan.asset_class_id) if m.pk not in assigned_model_ids
    ]

    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(
        request,
        "maintenance/components/_plan_models_dlb_only.html",
        {
            "plan": plan,
            "models_available": models_available,
            "models_assigned": assigned_models,
        },
    ).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["GET", "POST"])
def plan_worklist(request: HttpRequest, pk: int) -> HttpResponse:
    plan = get_object_or_404(
        MaintenancePlan.objects.select_related(
            "domain", "asset_class", "template_action_set"
        ).prefetch_related("asset_models"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, plan.domain_id):
        raise Http404

    ctx = MaintenancePlanContext(pk)

    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "create_event":
                asset_id_raw = request.POST.get("asset_id", "").strip()
                if not asset_id_raw.isdigit():
                    messages.error(request, "Choose an asset.")
                else:
                    detail = ctx.create_maintenance_event(
                        asset_id=int(asset_id_raw), actor=request.user
                    )
                    messages.success(request, f"Maintenance event #{detail.pk} created.")
            elif action == "create_all":
                results = MaintenancePlanner.plan_for(plan)
                created = MaintenancePlanner.create_events_from_results(
                    results, actor=request.user
                )
                messages.success(
                    request,
                    f"{len(created)} maintenance event(s) generated."
                    if created
                    else "No assets are currently due under this plan.",
                )
            else:
                messages.error(request, "Unknown action.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("plan_worklist", kwargs={"pk": pk}))

    due = MaintenancePlanner.plan_for(plan) if plan.status == PlanStatus.ACTIVE else []
    template = plan.template_action_set
    items = (
        list(
            template.template_action_items.filter(deleted_at__isnull=True).order_by(
                "sequence_order"
            )
        )
        if template
        else []
    )
    return render(
        request,
        "maintenance/planning/worklist.html",
        {
            "plan": plan,
            "due": due,
            "due_count": len(due),
            "template": template,
            "items": items,
            "meter_plan_unevaluated": plan.frequency_type != PlanFrequencyType.CALENDAR,
        },
    )


def _template_results(request: HttpRequest) -> HttpResponse:
    """Click-to-search template picker results."""
    from django.db.models import Count, Q

    q = request.GET.get("q", "").strip()
    qs = TemplateActionSet.objects.filter(
        domain_id__in=accessible_domain_ids(request),
        deleted_at__isnull=True,
        is_active=True,
    ).annotate(action_count=Count("template_action_items"))
    if q:
        qs = qs.filter(Q(task_name__icontains=q) | Q(description__icontains=q))
    return render(
        request,
        "maintenance/planning/_template_results.html",
        {"templates": qs.order_by("task_name")[:25]},
    )
