"""Maintenance event index / detail / create entrypoints.

Legacy: presentation/routes/maintenance/main.py. A "maintenance event" here is
an events.MaintenanceDetail row (MTI). Creation always goes through
MaintenanceFactory.create_from_template — Action/ActionTool/PartDemand rows
are expanded from the chosen TemplateActionSet in one atomic transaction (R2),
so there is no per-action wizard step at creation time. A blank event with no
template is also supported; actions are then added one at a time from the
detail page (action_views.action_create).
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventPriority, EventStatus
from app.maintenance.control_layer.domain_structs.maintenance_detail_struct import (
    MaintenanceDetailStruct,
)
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.control_layer.maintenance_factory import MaintenanceFactory
from app.maintenance.models.asset_limitation import CapabilityStatus
from app.maintenance.models.blocker import BlockerPriority
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.search.maintenance_search import (
    MaintenanceSearch,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)

PAGE_SIZE = 25


def _detail_or_404_in_domain(request: HttpRequest, pk: int) -> MaintenanceDetail:
    """D5: an event outside the user's domain access is not reachable at all."""
    detail = get_object_or_404(
        MaintenanceDetail.objects.select_related(
            "domain", "asset", "assigned_user", "template_action_set"
        ),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, detail.domain_id):
        raise Http404
    return detail


@require_http_methods(["GET"])
def maintenance_index(request: HttpRequest) -> HttpResponse:
    """Maintenance Hub Index (index.html) — status filters, Rule #5 compliant
    empty states. `format=` supports density (condensed/medium/large) and the
    htmx-search-results fragment (endpoint_patterns.md §3.5)."""
    domain_ids = accessible_domain_ids(request)

    status = request.GET.get("status", "").strip()
    asset_id_raw = request.GET.get("asset_id", "").strip()
    asset_id = int(asset_id_raw) if asset_id_raw.isdigit() else None
    priority = request.GET.get("priority", "").strip()
    maintenance_type = request.GET.get("maintenance_type", "").strip()
    work_order_reference = request.GET.get("work_order_reference", "").strip()
    my_work = request.GET.get("my_work", "").strip() == "1"
    q = request.GET.get("q", "").strip()

    qs = MaintenanceSearch.index_list(
        domain_ids=domain_ids,
        status=status,
        asset_id=asset_id,
        priority=priority,
        maintenance_type=maintenance_type,
        work_order_reference=work_order_reference,
        assigned_user_id=request.user.pk if my_work else None,
        q=q,
    )

    density = request.GET.get("format", "condensed")
    if density not in ("condensed", "medium", "large"):
        density = "condensed"

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "events": page.object_list,
        "density": density,
        "filters": {
            "status": status,
            "asset_id": asset_id_raw,
            "priority": priority,
            "maintenance_type": maintenance_type,
            "work_order_reference": work_order_reference,
            "my_work": "1" if my_work else "",
            "q": q,
        },
        "statuses": EventStatus.choices,
        "priorities": EventPriority.choices,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
    }

    if request.GET.get("format") == "htmx-search-results":
        return render(request, "maintenance/components/_index_results.html", context)
    return render(request, "maintenance/index.html", context)


@require_http_methods(["GET", "POST"])
def maintenance_create(request: HttpRequest) -> HttpResponse:
    """Single-card create form (not a wizard — MaintenanceFactory expands the
    template's actions/tools/part-demands atomically; the user is not asked to
    pick actions one by one at creation time)."""
    user_domain_ids = list(request.user.get_all_domain_ids())

    if request.method == "POST":
        domain_id_raw = request.POST.get("domain_id", "").strip()
        domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None
        if domain_id not in user_domain_ids:
            messages.error(
                request, "You may only create a maintenance event in a domain you are assigned to."
            )
            return redirect(reverse("maintenance_create"))

        asset_id_raw = request.POST.get("asset_id", "").strip()
        asset_id = int(asset_id_raw) if asset_id_raw.isdigit() else None
        template_id_raw = request.POST.get("template_action_set_id", "").strip()
        template_id = int(template_id_raw) if template_id_raw.isdigit() else None
        title = request.POST.get("title", "").strip()
        maintenance_type = request.POST.get("maintenance_type", "").strip()
        work_order_reference = request.POST.get("work_order_reference", "").strip()
        priority = request.POST.get("priority", "").strip() or None
        event_start_raw = request.POST.get("event_start", "").strip()
        event_start = None
        if event_start_raw:
            from django.utils.dateparse import parse_datetime

            event_start = parse_datetime(event_start_raw)

        if not template_id:
            messages.error(request, "A procedure template is required to create a maintenance event.")
            return redirect(reverse("maintenance_create"))

        try:
            detail = MaintenanceFactory.create_from_template(
                template_action_set_id=template_id,
                domain_id=domain_id,
                asset_id=asset_id,
                title=title or None,
                maintenance_type=maintenance_type,
                work_order_reference=work_order_reference,
                event_start=event_start or timezone.now(),
                priority=priority,
                assigned_user=request.user,
                assigned_by=request.user,
                actor=request.user,
            )
        except TemplateActionSet.DoesNotExist:
            messages.error(request, "Selected template not found.")
            return redirect(reverse("maintenance_create"))

        messages.success(request, f"Maintenance event #{detail.pk} created.")
        return redirect(reverse("maintenance_detail", kwargs={"pk": detail.pk}))

    domains = Domain.objects.filter(pk__in=user_domain_ids).order_by("name")
    templates = TemplateActionSet.objects.filter(
        domain_id__in=user_domain_ids, deleted_at__isnull=True, is_active=True
    ).order_by("task_name")
    default_event_start = timezone.now().strftime("%Y-%m-%dT%H:%M")
    return render(
        request,
        "maintenance/create.html",
        {
            "domains": domains,
            "show_domain_picker": domains.count() > 1,
            "single_domain": domains.first() if domains.count() == 1 else None,
            "templates": templates,
            "priorities": EventPriority.choices,
            "default_event_start": default_event_start,
        },
    )


@require_http_methods(["GET", "POST"])
def maintenance_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Parent event info, action step list, blocker section, part demand
    status (detail.html). Every mutation posts back to this same canonical
    URL with a distinct `action` (endpoint_patterns.md §3.3)."""
    detail = _detail_or_404_in_domain(request, pk)
    ctx = MaintenanceContext(pk)

    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "start":
                ctx.start(actor=request.user)
                messages.success(request, "Event started.")
            elif action == "complete":
                ctx.complete(actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Event marked complete.")
            elif action == "cancel":
                ctx.cancel(actor=request.user, notes=request.POST.get("notes", ""))
                messages.success(request, "Event cancelled.")
            elif action == "add_blocker":
                ctx.blocker_manager.add_blocker(
                    reason=request.POST.get("reason", ""),
                    notes=request.POST.get("notes", ""),
                    priority=request.POST.get("priority", BlockerPriority.MEDIUM),
                    actor=request.user,
                )
                messages.success(request, "Blocker logged.")
            elif action == "end_blocker":
                blocker_id = int(request.POST.get("blocker_id", 0))
                ctx.blocker_manager.end_blocker(blocker_id=blocker_id, actor=request.user)
                messages.success(request, "Blocker resolved.")
            elif action == "add_limitation":
                ctx.limitation_manager.create_record(
                    status=request.POST.get("status", CapabilityStatus.NON_CAPABLE),
                    limitation_description=request.POST.get("limitation_description", ""),
                    temporary_modifications=request.POST.get("temporary_modifications", ""),
                    actor=request.user,
                )
                messages.success(request, "Asset limitation record opened.")
            elif action == "close_limitation":
                record_id = int(request.POST.get("record_id", 0))
                ctx.limitation_manager.close_record(record_id=record_id, actor=request.user)
                messages.success(request, "Asset limitation record closed.")
            elif action == "set_billable_hours":
                value = float(request.POST.get("actual_billable_hours", 0) or 0)
                ctx.billable_hours_manager.set_actual_hours(value=value, actor=request.user)
                messages.success(request, "Billable hours updated.")
            elif action == "assign":
                from django.contrib.auth import get_user_model

                User = get_user_model()
                user_id = int(request.POST.get("assigned_user_id", 0) or 0)
                user = User.objects.get(pk=user_id)
                ctx.assignment_manager.assign(assigned_user=user, assigned_by=request.user)
                messages.success(request, f"Assigned to {user}.")
            elif action == "add_comment":
                ctx.add_comment(request.POST, actor=request.user)
                messages.success(request, "Comment added.")
            else:
                messages.error(request, "Unknown action.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("maintenance_detail", kwargs={"pk": pk}))

    struct = MaintenanceDetailStruct.load(maintenance_detail_id=pk)
    completion_verdict = ctx.completion_verdict()
    context = {
        "detail": detail,
        "struct": struct,
        "actions": struct.actions,
        "blockers": struct.blockers,
        "limitation_records": struct.limitation_records,
        "completion_verdict": completion_verdict,
        "billable_hours_manager": ctx.billable_hours_manager,
        "billable_hours_warning": ctx.billable_hours_manager.get_warning(),
        "blocker_priorities": BlockerPriority.choices,
        "capability_statuses": CapabilityStatus.choices,
        "can_edit": is_in_domain(request, detail.domain_id),
    }

    if request.GET.get("format") == "htmx-focused":
        return render(request, "maintenance/components/_action_list.html", context)
    return render(request, "maintenance/detail.html", context)
