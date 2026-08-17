"""Action step entrypoints — create, status transitions, reorder, tool/part-demand
attachment. Legacy: presentation/routes/maintenance/action_creator_portal.py.

Actions are a child collection of one MaintenanceDetail (endpoint_patterns.md
§3.4): `maintenance/event/<id>/actions` for create, `maintenance/action/<id>`
for single-action operations. Every write here re-renders the WHOLE parent
event page (htmx_patterns.md §2.B "Adding data to existing items") so side
effects (billable-hours totals, completion-gate state) are always current —
callers use `hx-select="#action-list"` to pull just the list back out.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.maintenance.control_layer.action_context import ActionContext
from app.maintenance.control_layer.action_tool_manager import ActionToolManager
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.presentation_layer.tools.maintenance_access import is_in_domain


def _action_or_404_in_domain(request: HttpRequest, action_id: int) -> Action:
    action = get_object_or_404(
        Action.objects.select_related("event_detail__domain"),
        pk=action_id,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, action.event_detail.domain_id):
        raise Http404
    return action


@require_http_methods(["POST"])
def action_create(request: HttpRequest, maintenance_id: int) -> HttpResponse:
    """POST-only child-collection create — the parent is identified only by
    the URL (endpoint_patterns.md §3.4). `source` selects blank / proto-library
    / duplicate-of-sibling; template-based expansion happens only at event
    creation time (MaintenanceFactory), not one action at a time here."""
    ctx = MaintenanceContext(maintenance_id)
    if not is_in_domain(request, ctx.maintenance_detail.domain_id):
        raise Http404

    source = request.POST.get("source", "blank")
    insert_position = request.POST.get("insert_position", "end")
    after_action_id_raw = request.POST.get("after_action_id", "").strip()
    after_action_id = int(after_action_id_raw) if after_action_id_raw.isdigit() else None

    try:
        if source == "proto":
            proto_id = int(request.POST.get("proto_action_item_id", 0))
            ctx.action_creation_manager.create_from_proto_action_item(
                proto_action_item_id=proto_id,
                insert_position=insert_position,
                after_action_id=after_action_id,
                copy_part_demands=True,
                copy_tools=True,
                actor=request.user,
            )
        elif source == "duplicate":
            source_action_id = int(request.POST.get("source_action_id", 0))
            ctx.action_creation_manager.duplicate(
                source_action_id=source_action_id,
                insert_position=insert_position,
                after_action_id=after_action_id,
                copy_part_demands=True,
                copy_tools=True,
                actor=request.user,
            )
        else:
            ctx.action_creation_manager.create_blank(
                action_name=request.POST.get("action_name", "").strip(),
                description=request.POST.get("description", ""),
                instructions=request.POST.get("instructions", ""),
                estimated_duration_minutes=(
                    int(request.POST["estimated_duration_minutes"])
                    if request.POST.get("estimated_duration_minutes", "").strip().isdigit()
                    else None
                ),
                insert_position=insert_position,
                after_action_id=after_action_id,
                actor=request.user,
            )
        messages.success(request, "Action added.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("maintenance_detail", kwargs={"pk": maintenance_id}))


@require_http_methods(["POST"])
def action_update(request: HttpRequest, action_id: int) -> HttpResponse:
    """Single action row (endpoint_patterns.md §3.4 child detail): status
    transitions, plain-field edit, and assignment all post here."""
    action = _action_or_404_in_domain(request, action_id)
    ctx = ActionContext(action_id)
    transition = request.POST.get("transition", "")

    try:
        if transition == "start":
            ctx.start(actor=request.user)
        elif transition == "complete":
            hours_raw = request.POST.get("billable_hours", "").strip()
            ctx.complete(
                actor=request.user,
                billable_hours=float(hours_raw) if hours_raw else None,
                notes=request.POST.get("completion_notes", ""),
            )
            MaintenanceContext(action.event_detail_id).billable_hours_manager.auto_update_if_greater(
                actor=request.user
            )
        elif transition == "fail":
            hours_raw = request.POST.get("billable_hours", "").strip()
            ctx.mark_failed(
                actor=request.user,
                billable_hours=float(hours_raw) if hours_raw else None,
                notes=request.POST.get("completion_notes", ""),
            )
        elif transition == "skip":
            ctx.mark_skipped(actor=request.user, notes=request.POST.get("completion_notes", ""))
        elif transition == "edit":
            duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
            ctx.edit(
                actor=request.user,
                action_name=request.POST.get("action_name") or None,
                description=request.POST.get("description"),
                instructions=request.POST.get("instructions"),
                notes=request.POST.get("notes"),
                estimated_duration_minutes=int(duration_raw) if duration_raw.isdigit() else None,
            )
        elif transition == "assign":
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user_id_raw = request.POST.get("assigned_user_id", "").strip()
            if user_id_raw.isdigit():
                user = User.objects.get(pk=int(user_id_raw))
                ctx.assign(assigned_user=user, assigned_by=request.user, actor=request.user)
        elif transition == "add_tool":
            ActionToolManager.create_for_action(
                action_id=action_id,
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
                actor=request.user,
            )
        elif transition == "remove_tool":
            ActionToolManager.delete(
                action_tool_id=int(request.POST.get("action_tool_id", 0)), actor=request.user
            )
        elif transition == "add_part_demand":
            from decimal import Decimal

            PartDemandManager.create_for_action(
                action_id=action_id,
                part_id=int(request.POST.get("part_id", 0)),
                quantity_requested=Decimal(request.POST.get("quantity_requested", "1") or "1"),
                notes=request.POST.get("notes", ""),
                actor=request.user,
            )
        elif transition == "remove_part_demand":
            PartDemandManager.remove_link(
                link_id=int(request.POST.get("link_id", 0)), actor=request.user
            )
        else:
            messages.error(request, "Unknown action transition.")
        messages.success(request, "Action updated.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("maintenance_detail", kwargs={"pk": action.event_detail_id}))


@require_http_methods(["POST"])
def action_reorder(request: HttpRequest, action_id: int) -> HttpResponse:
    action = _action_or_404_in_domain(request, action_id)
    ctx = ActionContext(action_id)
    try:
        new_order = int(request.POST.get("sequence_order", 0))
        ctx.reorder(new_sequence_order=new_order, actor=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("maintenance_detail", kwargs={"pk": action.event_detail_id}))
