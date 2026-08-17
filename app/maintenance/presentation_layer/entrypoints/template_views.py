"""Procedure template library + the session-backed template builder wizard.

Legacy: presentation/routes/maintenance/template_portal.py. The builder is one
scrolling page (multi_step_flows.md) backed entirely by
TemplateBuilderSessionAdapter / request.session['template_builder_draft'] —
zero DB writes until `template_builder_commit`. Every sub-mutation (add
action, add tool, add part demand, remove, reorder) posts to
`template_builder_update` and redirects back to the GET, so F5 always shows
the current draft (htmx_patterns.md §2.C).
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.maintenance.control_layer.adapters.template_builder_session_adapter import (
    TemplateBuilderSessionAdapter,
)
from app.maintenance.control_layer.template_maintenance_context import (
    TemplateMaintenanceContext,
)
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)


@require_http_methods(["GET"])
def template_index(request: HttpRequest) -> HttpResponse:
    """Procedure template library index (D5-scoped)."""
    domain_ids = accessible_domain_ids(request)
    q = request.GET.get("q", "").strip()
    qs = TemplateActionSet.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).select_related("domain", "asset_class", "asset_model")
    if q:
        qs = qs.filter(task_name__icontains=q)
    templates = qs.order_by("task_name")
    return render(
        request,
        "maintenance/template_index.html",
        {"templates": templates, "q": q},
    )


@require_http_methods(["GET"])
def template_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Read-only view of a committed procedure template."""
    template = get_object_or_404(
        TemplateActionSet.objects.select_related("domain", "asset_class", "asset_model"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, template.domain_id):
        raise Http404
    tctx = TemplateMaintenanceContext(pk)
    context = {
        "template": template,
        "items": tctx.template_action_items,
        "tools_by_action": tctx.get_tools_by_action(),
        "part_demands_by_action": tctx.get_part_demands_by_action(),
        "total_estimated_duration_minutes": tctx.total_estimated_duration_minutes,
    }
    return render(request, "maintenance/template_detail.html", context)


@require_http_methods(["GET", "POST"])
def template_builder(request: HttpRequest) -> HttpResponse:
    """The single-scroll wizard page. GET renders the draft; POST with
    `action=start_revision` or `action=start_blank` (re)seeds it; the actual
    per-field mutations live in template_builder_update."""
    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "start_revision":
            template_id = int(request.POST.get("template_action_set_id", 0))
            TemplateBuilderSessionAdapter.start_revision(
                request, template_action_set_id=template_id
            )
            messages.success(request, "Draft seeded from existing template.")
        elif action == "start_blank":
            adapter = TemplateBuilderSessionAdapter(request)
            adapter.clear()
            TemplateBuilderSessionAdapter(request)  # reseed a blank draft
            messages.success(request, "Started a new blank draft.")
        return redirect(reverse("template_builder"))

    adapter = TemplateBuilderSessionAdapter(request)
    user_domain_ids = list(request.user.get_all_domain_ids())
    context = {
        "draft": adapter.draft,
        "domains": Domain.objects.filter(pk__in=user_domain_ids).order_by("name"),
        "show_domain_picker": len(user_domain_ids) > 1,
        "single_domain_id": user_domain_ids[0] if len(user_domain_ids) == 1 else None,
        "proto_items": ProtoActionItem.objects.filter(
            domain_id__in=user_domain_ids, deleted_at__isnull=True
        ).order_by("action_name"),
        "existing_templates": TemplateActionSet.objects.filter(
            domain_id__in=user_domain_ids, deleted_at__isnull=True, is_active=True
        ).order_by("task_name"),
    }
    return render(request, "maintenance/template_builder.html", context)


@require_http_methods(["POST"])
def template_builder_update(request: HttpRequest) -> HttpResponse:
    """Session-only mutation endpoint (multi_step_flows.md's session-draft
    pattern) — never touches the database. Redirects back to the builder GET
    so the F5 rule holds."""
    adapter = TemplateBuilderSessionAdapter(request)
    action = request.POST.get("action", "")

    try:
        if action == "set_metadata":
            adapter.set_metadata(
                task_name=request.POST.get("task_name", "").strip(),
                description=request.POST.get("description", ""),
                asset_class_id=(
                    int(request.POST["asset_class_id"])
                    if request.POST.get("asset_class_id", "").strip().isdigit()
                    else None
                ),
                asset_model_id=(
                    int(request.POST["asset_model_id"])
                    if request.POST.get("asset_model_id", "").strip().isdigit()
                    else None
                ),
            )
        elif action == "add_action":
            duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
            adapter.add_action(
                action_name=request.POST.get("action_name", "").strip(),
                description=request.POST.get("description", ""),
                instructions=request.POST.get("instructions", ""),
                safety_notes=request.POST.get("safety_notes", ""),
                notes=request.POST.get("notes", ""),
                estimated_duration_minutes=int(duration_raw) if duration_raw.isdigit() else None,
            )
        elif action == "add_action_from_proto":
            adapter.add_action_from_proto(
                proto_action_item_id=int(request.POST.get("proto_action_item_id", 0))
            )
        elif action == "remove_action":
            adapter.remove_action(temp_id=request.POST.get("temp_id", ""))
        elif action == "add_tool":
            adapter.add_tool(
                temp_id=request.POST.get("temp_id", ""),
                tool_id=(
                    int(request.POST["tool_id"])
                    if request.POST.get("tool_id", "").strip().isdigit()
                    else None
                ),
                tool_name=request.POST.get("tool_name", ""),
                quantity_required=int(request.POST.get("quantity_required", 1) or 1),
                specifications=request.POST.get("specifications", ""),
                notes=request.POST.get("notes", ""),
                is_required=request.POST.get("is_required") == "on",
            )
        elif action == "remove_tool":
            adapter.remove_tool(
                temp_id=request.POST.get("temp_id", ""),
                tool_index=int(request.POST.get("tool_index", -1)),
            )
        elif action == "add_part_demand":
            adapter.add_part_demand(
                temp_id=request.POST.get("temp_id", ""),
                part_id=int(request.POST.get("part_id", 0)),
                quantity_required=float(request.POST.get("quantity_required", 1) or 1),
                notes=request.POST.get("notes", ""),
                is_optional=request.POST.get("is_optional") == "on",
            )
        elif action == "remove_part_demand":
            adapter.remove_part_demand(
                temp_id=request.POST.get("temp_id", ""),
                demand_index=int(request.POST.get("demand_index", -1)),
            )
        elif action == "clear":
            adapter.clear()
            messages.success(request, "Draft cleared.")
        else:
            messages.error(request, "Unknown draft action.")
    except (ValueError, KeyError) as exc:
        messages.error(request, str(exc))

    return redirect(reverse("template_builder"))


@require_http_methods(["POST"])
def template_builder_commit(request: HttpRequest) -> HttpResponse:
    """The one path that touches the database — atomic commit of the whole
    draft (R2)."""
    adapter = TemplateBuilderSessionAdapter(request)
    user_domain_ids = list(request.user.get_all_domain_ids())
    domain_id_raw = request.POST.get("domain_id", "").strip()
    domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None

    if domain_id not in user_domain_ids:
        messages.error(request, "You may only publish a template into a domain you are assigned to.")
        return redirect(reverse("template_builder"))

    try:
        template = adapter.commit(domain_id=domain_id, actor=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("template_builder"))

    messages.success(request, f"Template '{template.task_name}' published.")
    return redirect(reverse("template_detail", kwargs={"pk": template.pk}))
