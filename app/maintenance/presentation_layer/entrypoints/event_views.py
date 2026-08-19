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

from app.administration.models import Domain, User
from app.assets.models import AssetClass, AssetModel, Manufacturer
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventPriority, EventStatus
from app.events.presentation_layer.tools.generic_cards import build_activity_card
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


def _assigned_technicians(detail: MaintenanceDetail, actions) -> list[dict]:
    """Group event-level + per-action assignments by user for the read-only
    view's Assigned Technicians card. Event lead (detail.assigned_user, if
    any) is always listed first."""
    groups: dict[int, dict] = {}
    if detail.assigned_user_id:
        groups[detail.assigned_user_id] = {
            "user": detail.assigned_user,
            "is_lead": True,
            "actions": [],
        }
    for action in actions:
        if not action.assigned_user_id:
            continue
        entry = groups.setdefault(
            action.assigned_user_id,
            {"user": action.assigned_user, "is_lead": False, "actions": []},
        )
        entry["actions"].append(action)
    return list(groups.values())


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
    htmx-search-results fragment (endpoint_patterns.md §3.5). Preview mode
    (?preview=1) adds a list/preview split with the event details on the
    preview pane."""
    domain_ids = accessible_domain_ids(request)

    status = request.GET.get("status", "").strip()
    asset_id_raw = request.GET.get("asset_id", "").strip()
    asset_id = int(asset_id_raw) if asset_id_raw.isdigit() else None
    priority = request.GET.get("priority", "").strip()
    maintenance_type = request.GET.get("maintenance_type", "").strip()
    work_order_reference = request.GET.get("work_order_reference", "").strip()
    my_work = request.GET.get("my_work", "").strip() == "1"
    q = request.GET.get("q", "").strip()
    domain_raw = request.GET.get("domain", "").strip()
    domain_filter = int(domain_raw) if domain_raw.isdigit() else None
    asset_class = request.GET.get("asset_class", "").strip()
    model = request.GET.get("model", "").strip()
    manufacturer = request.GET.get("manufacturer", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    has_blockers = request.GET.get("has_blockers", "").strip() == "1"
    has_limitations = request.GET.get("has_limitations", "").strip() == "1"
    action_title = request.GET.get("action_title", "").strip()
    created_by_raw = request.GET.get("created_by", "").strip()
    created_by_id = int(created_by_raw) if created_by_raw.isdigit() else None
    commented_by_raw = request.GET.get("commented_by", "").strip()
    commented_by_id = int(commented_by_raw) if commented_by_raw.isdigit() else None
    assigned_to_raw = request.GET.get("assigned_to", "").strip()
    assigned_to_id = int(assigned_to_raw) if assigned_to_raw.isdigit() else None
    preview = request.GET.get("preview", "").strip()
    preview_mode = preview == "1"
    selected_id_raw = request.GET.get("selected", "").strip()

    qs = MaintenanceSearch.index_list(
        domain_ids=domain_ids,
        status=status,
        asset_id=asset_id,
        priority=priority,
        maintenance_type=maintenance_type,
        work_order_reference=work_order_reference,
        assigned_user_id=request.user.pk if my_work else assigned_to_id,
        q=q,
        domain_id=domain_filter,
        asset_class=asset_class,
        model=model,
        manufacturer=manufacturer,
        date_from=date_from or None,
        date_to=date_to or None,
        has_blockers=has_blockers,
        has_limitations=has_limitations,
        action_title=action_title,
        created_by_id=created_by_id,
        commented_by_id=commented_by_id,
    )

    density = request.GET.get("format", "condensed")
    if density not in ("condensed", "medium", "large"):
        density = "condensed"

    paginator = Paginator(qs, PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    # The preview pane — never blank; auto-select first event if none chosen.
    selected = None
    struct = None
    if preview_mode:
        selected_id = None
        if selected_id_raw.isdigit():
            selected_id = int(selected_id_raw)
        elif page.object_list:
            selected_id = page.object_list[0].pk

        if selected_id:
            try:
                selected = _detail_or_404_in_domain(request, selected_id)
                struct = MaintenanceDetailStruct.load(maintenance_detail_id=selected_id)
            except Http404:
                pass

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
            "domain": domain_raw,
            "asset_class": asset_class,
            "model": model,
            "manufacturer": manufacturer,
            "date_from": date_from,
            "date_to": date_to,
            "has_blockers": "1" if has_blockers else "",
            "has_limitations": "1" if has_limitations else "",
            "action_title": action_title,
            "created_by": created_by_raw,
            "commented_by": commented_by_raw,
            "assigned_to": assigned_to_raw,
            "preview": preview,
            "selected": selected_id_raw,
        },
        "statuses": EventStatus.choices,
        "priorities": EventPriority.choices,
        "maintenance_types": MaintenanceDetail._meta.get_field("maintenance_type").choices,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "classes": AssetClass.objects.order_by("name"),
        "models": AssetModel.objects.order_by("model_name", "version_rank", "version"),
        "manufacturers": Manufacturer.objects.order_by("name"),
        "users": User.objects.filter(is_active=True).order_by("username"),
        "preview_mode": preview_mode,
        "selected": selected,
        "struct": struct,
    }

    results_template = (
        "maintenance/_maintenance_index_preview_split.html"
        if preview_mode
        else "maintenance/components/_index_results.html"
    )
    if request.GET.get("format") == "htmx-search-results":
        return render(request, results_template, context)
    return render(request, "maintenance/index.html", context)


@require_http_methods(["GET", "POST"])
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
                ctx.blocker_manager.end_blocker(
                    blocker_id=blocker_id,
                    resolution_notes=request.POST.get("resolution_notes", ""),
                    actor=request.user,
                )
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
                ctx.limitation_manager.close_record(
                    record_id=record_id,
                    resolution_notes=request.POST.get("resolution_notes", ""),
                    actor=request.user,
                )
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
        # Drive the above-the-fold "work is blocked" / "asset is limited"
        # banners — the two facts a reader must see before anything else.
        "active_blockers": struct.active_blockers,
        "active_limitations": struct.active_limitation_records,
        "completion_verdict": completion_verdict,
        "billable_hours_manager": ctx.billable_hours_manager,
        "billable_hours_warning": ctx.billable_hours_manager.get_warning(),
        "blocker_priorities": BlockerPriority.choices,
        "capability_statuses": CapabilityStatus.choices,
        "can_edit": is_in_domain(request, detail.domain_id),
        "activity_card": build_activity_card(detail, request.user),
        "assigned_technicians": _assigned_technicians(detail, struct.actions),
        "part_demand_rows": [
            {"action": action, "link": link}
            for action in struct.actions
            for link in action.demand_links.all()
        ],
    }

    if request.GET.get("format") == "htmx-focused":
        return render(request, "maintenance/components/_action_list.html", context)
    return render(request, "maintenance/detail.html", context)
