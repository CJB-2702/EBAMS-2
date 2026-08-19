"""Create & Assign portal and the unassigned-event queue.

Legacy: user_views/manager/create_assign.py.

The portal is one card holding three live search dropdowns — Template, Asset,
Technician — over a single POST that instantiates the event from the template
and assigns it in one step. The unassigned queue is the catch-up path for
events created without a technician, with bulk assignment over checked rows.

Assignment deliberately does not live in a modal
(harness/UX_UI/design_patterns/modals.md): both surfaces are in-page cards.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.assets.models import Asset
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventPriority, EventStatus
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.control_layer.maintenance_factory import MaintenanceFactory
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.entrypoints.work_views import technician_pool
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
)

User = get_user_model()

PAGE_SIZE = 50
BULK_LIMIT = 200

#: Statuses that mean the event is done with. Used to decide what counts as
#: "unassigned work still worth assigning" — a cancelled event with no
#: technician is not a gap in the schedule.
CLOSED_STATUSES = ("completed", "cancelled")


def _int(raw) -> int | None:
    raw = str(raw or "").strip()
    return int(raw) if raw.isdigit() else None


@require_http_methods(["GET", "POST"])
def create_assign(request: HttpRequest) -> HttpResponse:
    """The three-searchbar create card (legacy /manager/create-assign)."""
    domain_ids = accessible_domain_ids(request)
    user_domain_ids = list(request.user.get_all_domain_ids())

    fmt = request.GET.get("format", "")
    if fmt == "htmx-templates":
        return _template_results(request, domain_ids)
    if fmt == "htmx-assets":
        return _asset_results(request, domain_ids)
    if fmt == "htmx-technicians":
        return render(
            request,
            "maintenance/work/_technician_results.html",
            {"technicians": technician_pool(request, q=request.GET.get("q", ""))},
        )
    if fmt == "htmx-template-summary":
        return _template_summary(request, domain_ids)

    if request.method == "POST":
        return _handle_create(request, user_domain_ids=user_domain_ids)

    initial_template = TemplateActionSet.objects.filter(
        pk=_int(request.GET.get("template")),
        domain_id__in=domain_ids,
        deleted_at__isnull=True,
    ).first()
    initial_items = []
    if initial_template:
        initial_items = list(
            initial_template.template_action_items.filter(
                deleted_at__isnull=True
            ).order_by("sequence_order")
        )

    domains = Domain.objects.filter(pk__in=user_domain_ids).order_by("name")
    return render(
        request,
        "maintenance/create_assign/portal.html",
        {
            "domains": domains,
            "show_domain_picker": domains.count() > 1,
            "single_domain": domains.first() if domains.count() == 1 else None,
            "priorities": EventPriority.choices,
            "default_event_start": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "unassigned_count": _unassigned_qs(domain_ids).count(),
            "initial_template": initial_template,
            "initial_items": initial_items,
        },
    )


def _handle_create(request: HttpRequest, *, user_domain_ids) -> HttpResponse:
    template_id = _int(request.POST.get("template_action_set_id"))
    asset_id = _int(request.POST.get("asset_id"))
    domain_id = _int(request.POST.get("domain_id")) or (
        user_domain_ids[0] if len(user_domain_ids) == 1 else None
    )
    technician_id = _int(request.POST.get("assigned_user_id"))

    if domain_id not in user_domain_ids:
        messages.error(
            request, "You may only create a maintenance event in a domain you are assigned to."
        )
        return redirect(reverse("create_assign"))
    if not template_id:
        messages.error(request, "Choose a procedure template.")
        return redirect(reverse("create_assign"))

    start_raw = request.POST.get("event_start", "").strip()
    technician = User.objects.filter(pk=technician_id).first() if technician_id else None

    try:
        detail = MaintenanceFactory.create_from_template(
            template_action_set_id=template_id,
            domain_id=domain_id,
            asset_id=asset_id,
            title=request.POST.get("title", "").strip() or None,
            maintenance_type=request.POST.get("maintenance_type", "").strip(),
            work_order_reference=request.POST.get("work_order_reference", "").strip(),
            event_start=parse_datetime(start_raw) if start_raw else timezone.now(),
            priority=request.POST.get("priority", "").strip() or None,
            assigned_user=technician,
            assigned_by=request.user if technician else None,
            actor=request.user,
        )
    except TemplateActionSet.DoesNotExist:
        messages.error(request, "Selected template not found.")
        return redirect(reverse("create_assign"))

    if technician:
        messages.success(
            request, f"Event #{detail.pk} created and assigned to {technician}."
        )
    else:
        messages.success(
            request,
            f"Event #{detail.pk} created. It is unassigned — assign it from the "
            "unassigned queue when you know who is taking it.",
        )
    return redirect(reverse("maintenance_detail", kwargs={"pk": detail.pk}))


def _template_results(request: HttpRequest, domain_ids) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = TemplateActionSet.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True, is_active=True
    ).annotate(action_count=Count("template_action_items"))
    if q:
        qs = qs.filter(Q(task_name__icontains=q) | Q(description__icontains=q))
    return render(
        request,
        "maintenance/create_assign/_template_results.html",
        {"templates": qs.order_by("task_name")[:25]},
    )


def _asset_results(request: HttpRequest, domain_ids) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Asset.objects.all()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(serial_number__icontains=q))
    return render(
        request,
        "maintenance/create_assign/_asset_results.html",
        {"assets": qs.order_by("name")[:25]},
    )


def _template_summary(request: HttpRequest, domain_ids) -> HttpResponse:
    """The preview panel the legacy portal filled from
    api/template/<id>/summary once a template was picked."""
    template_id = _int(request.GET.get("template_action_set_id"))
    template = TemplateActionSet.objects.filter(
        pk=template_id, domain_id__in=domain_ids, deleted_at__isnull=True
    ).first()
    items = []
    if template:
        items = list(
            template.template_action_items.filter(deleted_at__isnull=True).order_by(
                "sequence_order"
            )
        )
    return render(
        request,
        "maintenance/create_assign/_template_summary.html",
        {"template": template, "items": items},
    )


# --------------------------------------------------------------------------- #
# Unassigned queue
# --------------------------------------------------------------------------- #


def _unassigned_qs(domain_ids):
    return (
        MaintenanceDetail.objects.filter(
            domain_id__in=domain_ids,
            deleted_at__isnull=True,
            assigned_user__isnull=True,
        )
        .exclude(status__in=CLOSED_STATUSES)
        .select_related("asset", "domain", "template_action_set")
    )


@require_http_methods(["GET", "POST"])
def unassigned_events(request: HttpRequest) -> HttpResponse:
    """The catch-up queue plus its bulk-assign card
    (legacy /manager/create-assign/unassigned)."""
    domain_ids = accessible_domain_ids(request)

    if request.method == "POST":
        return _handle_bulk_assign(request, domain_ids=domain_ids)

    if request.GET.get("format") == "htmx-technicians":
        return render(
            request,
            "maintenance/work/_technician_results.html",
            {"technicians": technician_pool(request, q=request.GET.get("q", ""))},
        )

    filters = {
        "status": request.GET.get("status", "").strip(),
        "priority": request.GET.get("priority", "").strip(),
        "asset_id": request.GET.get("asset_id", "").strip(),
        "q": request.GET.get("q", "").strip(),
    }

    qs = _unassigned_qs(domain_ids)
    if filters["status"]:
        qs = qs.filter(status=filters["status"])
    if filters["priority"]:
        qs = qs.filter(priority=filters["priority"])
    if _int(filters["asset_id"]):
        qs = qs.filter(asset_id=_int(filters["asset_id"]))
    if filters["q"]:
        qs = qs.filter(
            Q(title__icontains=filters["q"])
            | Q(work_order_reference__icontains=filters["q"])
            | Q(asset__name__icontains=filters["q"])
        )

    paginator = Paginator(qs.order_by("event_start"), PAGE_SIZE)
    page = paginator.get_page(request.GET.get("page", "1"))

    context = {
        "page": page,
        "events": page.object_list,
        "filters": filters,
        "statuses": EventStatus.choices,
        "priorities": EventPriority.choices,
    }
    if request.GET.get("format") == "htmx-search-results":
        return render(
            request, "maintenance/create_assign/_unassigned_results.html", context
        )
    return render(request, "maintenance/create_assign/unassigned.html", context)


def _handle_bulk_assign(request: HttpRequest, *, domain_ids) -> HttpResponse:
    target = request.POST.get("next") or reverse("unassigned_events")
    ids = [
        int(v) for v in request.POST.getlist("event_ids") if str(v).strip().isdigit()
    ]
    if not ids:
        messages.error(request, "No events were selected.")
        return redirect(target)
    if len(ids) > BULK_LIMIT:
        messages.error(request, f"Select at most {BULK_LIMIT} events at a time.")
        return redirect(target)

    user_id = _int(request.POST.get("assigned_user_id"))
    if not user_id:
        messages.error(request, "Choose a technician to assign to.")
        return redirect(target)
    technician = get_object_or_404(User, pk=user_id)
    notes = request.POST.get("notes", "").strip()

    # Re-fetch under the domain fence rather than trusting posted ids.
    events = MaintenanceDetail.objects.filter(
        pk__in=ids, domain_id__in=domain_ids, deleted_at__isnull=True
    )
    assigned = 0
    for event in events:
        MaintenanceContext(event.pk).assignment_manager.assign(
            assigned_user=technician, assigned_by=request.user
        )
        if notes:
            event.completion_notes = (
                f"{event.completion_notes}\nAssignment note: {notes}".strip()
                if event.completion_notes
                else f"Assignment note: {notes}"
            )
            event.updated_by = request.user
            event.save(update_fields=["completion_notes", "updated_by", "updated_at"])
        assigned += 1

    skipped = len(ids) - assigned
    if assigned:
        messages.success(request, f"{assigned} event(s) assigned to {technician}.")
    if skipped:
        messages.warning(
            request,
            f"{skipped} selected event(s) are outside your domains and were skipped.",
        )
    return redirect(target)
