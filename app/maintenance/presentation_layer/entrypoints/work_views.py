"""The three per-event portals the legacy app split across separate blueprints:
work, edit, and assign.

Legacy: core/work_portal.py, core/edit_portal.py, core/assign_portal.py.

The work portal is the technician's main screen — progress, per-step start /
edit / add-part, the two interruption types, and completion. The edit portal is
the manager's restructure screen — event metadata plus the action list and the
five-source action creator. The assign page is the single-event reassign path.

Every mutation posts back to its own canonical URL with a distinct `action`
(endpoint_patterns.md §3.3). All three are F5-safe: HTMX only ever re-renders
fragments these same views can render whole.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods

from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventPriority, EventStatus
from app.events.presentation_layer.tools.generic_cards import build_activity_card
from app.maintenance.control_layer.action_context import ActionContext
from app.maintenance.control_layer.action_tool_manager import ActionToolManager
from app.maintenance.control_layer.domain_structs.maintenance_detail_struct import (
    MaintenanceDetailStruct,
)
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.asset_limitation import CapabilityStatus
from app.maintenance.models.blocker import (
    BlockerPriority,
    BlockerReason,
    MaintenanceBlocker,
)
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)
from app.parts.models import Part, Tool
from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import DemandPriority, IssuanceState

User = get_user_model()


def _detail_or_404(request: HttpRequest, pk: int) -> MaintenanceDetail:
    detail = get_object_or_404(
        MaintenanceDetail.objects.select_related(
            "domain", "asset", "assigned_user", "template_action_set",
            "maintenance_plan", "meter_reading",
        ),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, detail.domain_id):
        raise Http404
    return detail


def _int(raw) -> int | None:
    raw = str(raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _decimal(raw) -> Decimal | None:
    raw = str(raw or "").strip()
    if not raw:
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def _datetime(raw):
    """Parse a <input type="datetime-local"> value into an aware datetime.

    The browser submits a naive wall clock ("2026-08-19T06:29"). With
    USE_TZ=True, handing that straight to the ORM stores it but warns, and
    leaves the interpretation implicit. Attach the project timezone here so
    the value means the same thing on the way in as it did on the way out.
    """
    parsed = parse_datetime(str(raw or "").strip() or "")
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _float(raw) -> float | None:
    raw = str(raw or "").strip()
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _required_notes(request: HttpRequest, message: str, *, field: str = "notes") -> str:
    """Every settling verb on a step (complete / skip / fail / block / reopen)
    carries a reason. The modal marks the field required, but a plain POST can
    always skip that, so the refusal is restated here."""
    notes = request.POST.get(field, "").strip()
    if not notes:
        raise ValueError(message)
    return notes


def _progress(actions) -> dict:
    """The work portal's status card numbers.

    The bar is SETTLED progress, not success rate — it answers "how much of
    this job still needs a decision from me", which is the question a
    technician standing at the asset actually has. So all three terminal
    outcomes fill it, in their own colour: green complete, red failed, grey
    skipped. A failed step is finished work; leaving its slice empty would
    read as "still to do" and understate how far the job has got.

    The per-outcome counts stay separate below, so nothing about the fill
    hides *which* outcome a step reached.
    """
    total = len(actions)
    complete = sum(1 for a in actions if a.status == ActionStatus.COMPLETE)
    in_progress = sum(1 for a in actions if a.status == ActionStatus.IN_PROGRESS)
    skipped = sum(1 for a in actions if a.status == ActionStatus.SKIPPED)
    failed = sum(1 for a in actions if a.status == ActionStatus.FAILED)
    blocked = sum(1 for a in actions if a.status == ActionStatus.BLOCKED)

    def pct(n: int) -> float:
        return round(100 * n / total, 2) if total else 0

    return {
        "total": total,
        "complete": complete,
        "in_progress": in_progress,
        "skipped": skipped,
        "failed": failed,
        "blocked": blocked,
        "settled": complete + failed + skipped,
        # Headline number: everything that reached an outcome.
        "percent": int(round(100 * (complete + failed + skipped) / total)) if total else 0,
        # Bar segment widths, which must sum to `percent`.
        "percent_complete": pct(complete),
        "percent_failed": pct(failed),
        "percent_skipped": pct(skipped),
    }


def _demand_rows(actions) -> dict[int, list]:
    """Per-action part demands, keyed by action id, for the per-step parts
    panel. Reaches outward through MaintenanceDemandLink (D7)."""
    from app.maintenance.models.demand_link import MaintenanceDemandLink

    rows: dict[int, list] = {}
    links = (
        MaintenanceDemandLink.objects.filter(
            action_id__in=[a.pk for a in actions], deleted_at__isnull=True
        )
        .select_related("part_demand", "part_demand__part")
        .order_by("sequence_order")
    )
    for link in links:
        rows.setdefault(link.action_id, []).append(link)
    return rows


def _tool_rows(actions) -> dict[int, list]:
    from app.maintenance.models.action_tool import ActionTool

    rows: dict[int, list] = {}
    for tool in ActionTool.objects.filter(
        action_id__in=[a.pk for a in actions], deleted_at__isnull=True
    ).select_related("tool"):
        rows.setdefault(tool.action_id, []).append(tool)
    return rows


def _attach_children(actions):
    """Hang the per-step parts and tools onto each action so the template does
    no dict indexing."""
    demands, tools = _demand_rows(actions), _tool_rows(actions)
    for action in actions:
        action.demand_rows = demands.get(action.pk, [])
        action.tool_rows = tools.get(action.pk, [])
    return actions


# --------------------------------------------------------------------------- #
# Work portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def maintenance_work(request: HttpRequest, pk: int) -> HttpResponse:
    """Perform maintenance (legacy /maintenance-event/<id>/work)."""
    detail = _detail_or_404(request, pk)

    if request.method == "POST":
        return _handle_work_post(request, detail)

    if request.GET.get("format") == "htmx-part-search":
        return _part_search_fragment(request)

    ctx = MaintenanceContext(pk)
    struct = MaintenanceDetailStruct.load(maintenance_detail_id=pk)
    actions = _attach_children(struct.actions)
    demand_rows = [(a, link) for a in actions for link in a.demand_rows]
    # "Actual start" is when work genuinely began, which is the earliest step
    # start_time — event_start is the PLANNED datetime and says nothing about
    # whether anyone has picked the job up.
    step_starts = [a.start_time for a in actions if a.start_time]

    context = {
        "actual_start": min(step_starts) if step_starts else None,
        "detail": detail,
        "struct": struct,
        "actions": actions,
        "progress": _progress(actions),
        "demand_rows": demand_rows,
        "total_parts": len(demand_rows),
        "total_tools": sum(len(a.tool_rows) for a in actions),
        "pending_approval_count": sum(
            1 for _, link in demand_rows
            if link.part_demand.demand_state in ("projected", "required")
        ),
        "blockers": struct.blockers,
        "active_blockers": struct.active_blockers,
        "limitation_records": struct.limitation_records,
        "active_limitations": struct.active_limitation_records,
        "completion_verdict": ctx.completion_verdict(),
        "billable_hours_warning": ctx.billable_hours_manager.get_warning(),
        "calculated_hours": ctx.billable_hours_manager.calculated_hours,
        "blocker_priorities": BlockerPriority.choices,
        "blocker_reasons": BlockerReason.choices,
        "event_priorities": EventPriority.choices,
        "capability_statuses": CapabilityStatus.choices,
        "demand_priorities": DemandPriority.choices,
        "issuance_states": IssuanceState.choices,
        "action_statuses": ActionStatus.choices,
        "activity_card": build_activity_card(detail, request.user),
    }

    if request.GET.get("format") == "htmx-actions":
        return render(request, "maintenance/work/_action_list.html", context)
    return render(request, "maintenance/work/work.html", context)


def _handle_work_post(request: HttpRequest, detail: MaintenanceDetail) -> HttpResponse:
    ctx = MaintenanceContext(detail.pk)
    action = request.POST.get("action", "")
    target = reverse("maintenance_work", kwargs={"pk": detail.pk})

    try:
        if action == "start_event":
            ctx.start(actor=request.user)
            messages.success(request, "Event started.")

        elif action == "complete_event":
            # Recording the final billable figure is part of closing the job,
            # so the completion dialog carries it rather than making the
            # technician set it separately before pressing complete.
            hours = _float(request.POST.get("actual_billable_hours"))
            if hours is not None:
                ctx.billable_hours_manager.set_actual_hours(
                    value=hours, actor=request.user
                )
            ctx.complete(actor=request.user, notes=request.POST.get("notes", ""))
            messages.success(request, "Event marked complete.")

        elif action == "start_action":
            # Start is the one verb with no confirmation step (no modal, no
            # notes): picking up a step is not a decision worth interrupting
            # for. Starting any step also starts the event, so the technician
            # never has to press "start" twice for the same act of beginning.
            ActionContext(_int(request.POST.get("action_id"))).start(actor=request.user)
            ctx.start(actor=request.user)
            messages.success(request, "Step started.")

        elif action == "complete_action":
            ActionContext(_int(request.POST.get("action_id"))).complete(
                actor=request.user,
                billable_hours=_float(request.POST.get("billable_hours")),
                notes=_required_notes(request, "Completion notes are required."),
            )
            messages.success(request, "Step completed.")

        elif action == "skip_action":
            ActionContext(_int(request.POST.get("action_id"))).mark_skipped(
                actor=request.user,
                notes=_required_notes(request, "A reason is required to skip a step."),
            )
            messages.success(request, "Step skipped.")

        elif action == "fail_action":
            ActionContext(_int(request.POST.get("action_id"))).mark_failed(
                actor=request.user,
                billable_hours=_float(request.POST.get("billable_hours")),
                notes=_required_notes(request, "A reason is required to fail a step."),
            )
            messages.warning(request, "Step marked failed.")

        elif action == "block_action":
            ActionContext(_int(request.POST.get("action_id"))).mark_blocked(
                actor=request.user,
                notes=_required_notes(request, "A reason is required to block a step."),
            )
            messages.warning(request, "Step blocked.")

        elif action == "reopen_action":
            ActionContext(_int(request.POST.get("action_id"))).reopen(
                actor=request.user,
                notes=_required_notes(request, "A reason is required to reopen a step."),
            )
            messages.success(request, "Step reopened and back in progress.")

        elif action == "edit_action":
            fields = {}
            for name in ("action_name", "description", "instructions", "completion_notes"):
                if name in request.POST:
                    fields[name] = request.POST.get(name, "")
            hours = request.POST.get("billable_hours", "").strip()
            if hours:
                fields["billable_hours"] = float(hours)
            ActionContext(_int(request.POST.get("action_id"))).edit(
                actor=request.user, **fields
            )
            messages.success(request, "Step updated.")

        elif action == "add_part_demand":
            PartDemandManager.create_for_action(
                action_id=_int(request.POST.get("action_id")),
                part_id=_int(request.POST.get("part_id")),
                quantity_requested=_decimal(request.POST.get("quantity")) or Decimal("1"),
                notes=request.POST.get("notes", ""),
                priority=request.POST.get("priority") or None,
                requested_by=request.user,
                actor=request.user,
            )
            messages.success(request, "Part demand raised.")

        elif action == "issue_part_demand":
            # Legacy's "Record Qty Issued": the technician states how much they
            # actually took, and the row moves to Issued Without Stock
            # Adjustment so supply can reconcile the movement later.
            qty = _decimal(request.POST.get("qty_issued"))
            PartDemandManager.record_technician_issue(
                demand_id=_int(request.POST.get("demand_id")),
                qty_issued=qty,
                actor=request.user,
                notes=request.POST.get("notes", ""),
            )
            messages.success(
                request,
                f"Recorded {qty} issued without a formal stock adjustment.",
            )

        elif action == "update_part_demand":
            demand_ctx = PartDemandContext(_int(request.POST.get("demand_id")))
            requested = _decimal(request.POST.get("quantity_requested"))
            if requested is not None:
                demand_ctx.update_fields(
                    quantity_requested=requested,
                    priority=request.POST.get("priority") or None,
                    actor=request.user,
                )
            to_stage = request.POST.get("issuance_state", "").strip()
            if to_stage and to_stage != demand_ctx.demand.issuance_state:
                qty = _decimal(request.POST.get("qty_issued"))
                if qty is not None and qty > 0:
                    PartDemandManager.record_technician_issue(
                        demand_id=demand_ctx.demand_id,
                        qty_issued=qty,
                        actor=request.user,
                        notes=request.POST.get("notes", ""),
                    )
                else:
                    demand_ctx.set_issuance_state(
                        to_stage=to_stage,
                        actor=request.user,
                        notes=request.POST.get("notes", ""),
                    )
            messages.success(request, "Part demand updated.")

        elif action == "cancel_part_demand":
            PartDemandContext(_int(request.POST.get("demand_id"))).cancel(
                actor=request.user,
                notes=_required_notes(
                    request, "A cancellation comment is required.", field="notes"
                ),
            )
            messages.success(request, "Part demand cancelled.")

        elif action == "approve_part_demand":
            PartDemandContext(_int(request.POST.get("demand_id"))).approve(
                actor=request.user, notes=request.POST.get("notes", "")
            )
            messages.success(request, "Part demand approved.")

        elif action == "reject_part_demand":
            PartDemandContext(_int(request.POST.get("demand_id"))).reject(
                actor=request.user, notes=request.POST.get("notes", "")
            )
            messages.success(request, "Part demand rejected.")

        elif action == "add_blocker":
            ctx.blocker_manager.add_blocker(
                reason=request.POST.get("reason", ""),
                notes=request.POST.get("notes", ""),
                start_date=_datetime(request.POST.get("start_date")),
                billable_hours_lost=_float(request.POST.get("billable_hours_lost")),
                priority=request.POST.get("priority", BlockerPriority.MEDIUM),
                expected_resolution_date=_datetime(request.POST.get("expected_resolution_date")),
                event_priority=request.POST.get("event_priority") or None,
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Work placed in blocked status.")

        elif action == "end_blocker":
            ctx.blocker_manager.end_blocker(
                blocker_id=_int(request.POST.get("blocker_id")),
                resolution_notes=_required_notes(
                    request,
                    "A resolution note is required to resolve a blocker.",
                    field="resolution_notes",
                ),
                start_date=_datetime(request.POST.get("start_date")),
                end_date=_datetime(request.POST.get("end_date")),
                billable_hours_lost=_float(request.POST.get("billable_hours_lost")),
                notes=request.POST.get("notes"),
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Blocker resolved.")

        elif action == "add_limitation":
            ctx.limitation_manager.create_record(
                status=request.POST.get("status", CapabilityStatus.NON_CAPABLE),
                limitation_description=request.POST.get("limitation_description", ""),
                temporary_modifications=request.POST.get("temporary_modifications", ""),
                start_time=_datetime(request.POST.get("start_time")),
                link_to_active_blocker=request.POST.get("link_to_blocker") == "true",
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Capability limitation opened.")

        elif action == "close_limitation":
            ctx.limitation_manager.close_record(
                record_id=_int(request.POST.get("record_id")),
                resolution_notes=_required_notes(
                    request,
                    "A resolution note is required to close a limitation.",
                    field="resolution_notes",
                ),
                start_time=_datetime(request.POST.get("start_time")),
                end_time=_datetime(request.POST.get("end_time")),
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Capability limitation closed.")

        # No standing "set_billable_hours" verb on this page. The work portal
        # records the final billable figure as part of complete_event above —
        # a separate always-open hours form on the work screen invited setting
        # it early and leaving it stale. The edit portal still has one.
        elif action == "add_comment":
            ctx.add_comment(request.POST, actor=request.user)
            messages.success(request, "Comment added.")

        else:
            messages.error(request, "Unknown action.")

    except ProcurementValidationError as exc:
        for error in exc.errors:
            messages.error(request, error)
    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))

    return redirect(target)


def _part_search_fragment(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Part.objects.all()
    if q:
        qs = qs.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    return render(
        request,
        "maintenance/part_demands/_part_search_results.html",
        {"parts": qs.order_by("part_number")[:25]},
    )


# --------------------------------------------------------------------------- #
# Edit portal
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def maintenance_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Restructure an event in flight (legacy /maintenance-event/<id>/edit).

    Hosts the Action Creator Portal's five sources. Note the asymmetry with
    templates: events are edited freely in place, templates are never edited,
    only revised.
    """
    detail = _detail_or_404(request, pk)

    if request.method == "POST":
        return _handle_edit_post(request, detail)

    fragment = request.GET.get("format", "")
    if fragment.startswith("htmx-creator"):
        return _action_creator_fragment(request, detail)
    if fragment == "htmx-action-editor":
        return _action_editor_panel_fragment(request, detail)

    struct = MaintenanceDetailStruct.load(maintenance_detail_id=pk)
    actions = _attach_children(struct.actions)
    selected_id = _int(request.GET.get("selected"))
    selected = next((a for a in actions if a.pk == selected_id), None)
    # Legacy defaults to the first action when nothing is explicitly selected
    # (render_edit_page: "Default to first action if none selected or
    # invalid") so the editor panel never opens empty when steps exist.
    if selected is None and actions:
        selected = actions[0]

    all_demands = [(a, link) for a in actions for link in a.demand_rows]
    all_tools = [(a, t) for a in actions for t in a.tool_rows]

    creator_tab = request.GET.get("tab", "template_set")
    creator_context = _creator_tab_context(request, detail, tab=creator_tab, q="")

    return render(
        request,
        "maintenance/work/edit.html",
        {
            **creator_context,
            "detail": detail,
            "struct": struct,
            "actions": actions,
            "selected_action": selected,
            "blockers": struct.blockers,
            "limitation_records": struct.limitation_records,
            "priorities": EventPriority.choices,
            "event_statuses": EventStatus.choices,
            "blocker_priorities": BlockerPriority.choices,
            "blocker_reasons": BlockerReason.choices,
            "capability_statuses": CapabilityStatus.choices,
            "action_statuses": ActionStatus.choices,
            "demand_priorities": DemandPriority.choices,
            "tools_catalog": Tool.objects.filter(is_active=True).order_by("name"),
            "parts_catalog": Part.objects.order_by("part_number"),
            "all_demands": all_demands,
            "all_tools": all_tools,
            "billable_hours_warning": MaintenanceContext(pk).billable_hours_manager.get_warning(),
            "activity_card": build_activity_card(detail, request.user),
            "creator_tab": creator_tab,
            "creator_url": reverse("maintenance_edit", kwargs={"pk": pk}),
            "tabs": CREATOR_TABS,
        },
    )


def _handle_edit_post(request: HttpRequest, detail: MaintenanceDetail) -> HttpResponse:
    ctx = MaintenanceContext(detail.pk)
    action = request.POST.get("action", "")
    target = reverse("maintenance_edit", kwargs={"pk": detail.pk})

    try:
        if action == "save_event":
            changed = []
            for name in ("title", "description", "maintenance_type",
                         "work_order_reference", "priority"):
                if name in request.POST:
                    setattr(detail, name, request.POST.get(name, ""))
                    changed.append(name)
            start_raw = request.POST.get("event_start", "").strip()
            if start_raw:
                detail.event_start = parse_datetime(start_raw)
                changed.append("event_start")
            end_raw = request.POST.get("event_end", "").strip()
            if end_raw:
                detail.event_end = parse_datetime(end_raw)
                changed.append("event_end")
            # "Additional Details": real MaintenanceDetail fields the legacy
            # edit page also exposed here. estimated_duration/safety_review_
            # required/staff_count/labor_hours/parts_cost are NOT included —
            # those live only on AbstractActionSet (TemplateActionSet), the
            # live event has no such columns (see abstract_mixins.py). Assignee
            # fields are deliberately omitted too — superseded by the dedicated
            # Assign page, which shows technician workload the way a bare
            # dropdown here never could.
            for name in ("completion_notes", "blocker_notes"):
                if name in request.POST:
                    setattr(detail, name, request.POST.get(name, ""))
                    changed.append(name)
            billable_raw = request.POST.get("actual_billable_hours", "").strip()
            if billable_raw:
                detail.actual_billable_hours = float(billable_raw)
                changed.append("actual_billable_hours")
            if changed:
                detail.updated_by = request.user
                detail.save(update_fields=changed + ["updated_by", "updated_at"])
            messages.success(request, "Event details saved.")

        # ── Force-set status, bypassing the guarded transition verbs ──────
        elif action == "force_set_status":
            new_status = request.POST.get("status", "").strip()
            valid_statuses = {value for value, _ in EventStatus.choices}
            if new_status not in valid_statuses:
                raise ValueError("Choose a valid status.")
            comment_text = _required_notes(
                request,
                "A comment is required to force a status change.",
                field="comment",
            )
            old_status_display = detail.get_status_display()
            detail.status = new_status
            detail.updated_by = request.user
            detail.save(update_fields=["status", "updated_by", "updated_at"])
            ctx.add_comment(
                {
                    "content": (
                        f"Status force-set from '{old_status_display}' to "
                        f"'{detail.get_status_display()}'. {comment_text}"
                    )
                },
                actor=request.user,
            )
            messages.success(request, f"Status forced to '{detail.get_status_display()}'.")

        # ── Delete the event outright ──────────────────────────────────────
        elif action == "delete_event":
            detail._soft_delete(actor=request.user)
            messages.success(request, "Event deleted.")
            return redirect(reverse("maintenance_index"))

        # ── Blockers / limitations, editable directly from this page ──────
        elif action == "add_blocker":
            ctx.blocker_manager.add_blocker(
                reason=request.POST.get("reason", ""),
                notes=request.POST.get("notes", ""),
                start_date=_datetime(request.POST.get("start_date")),
                billable_hours_lost=_float(request.POST.get("billable_hours_lost")),
                priority=request.POST.get("priority", BlockerPriority.MEDIUM),
                expected_resolution_date=_datetime(request.POST.get("expected_resolution_date")),
                event_priority=request.POST.get("event_priority") or None,
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Blocker logged.")

        elif action == "edit_blocker":
            ctx.blocker_manager.update_blocker(
                blocker_id=_int(request.POST.get("blocker_id")),
                reason=request.POST.get("reason"),
                priority=request.POST.get("priority"),
                billable_hours_lost=_float(request.POST.get("billable_hours_lost")),
                expected_resolution_date=_datetime(request.POST.get("expected_resolution_date")),
                notes=request.POST.get("notes"),
                actor=request.user,
            )
            messages.success(request, "Blocker updated.")

        elif action == "end_blocker":
            ctx.blocker_manager.end_blocker(
                blocker_id=_int(request.POST.get("blocker_id")),
                resolution_notes=_required_notes(
                    request,
                    "A resolution note is required to resolve a blocker.",
                    field="resolution_notes",
                ),
                start_date=_datetime(request.POST.get("start_date")),
                end_date=_datetime(request.POST.get("end_date")),
                billable_hours_lost=_float(request.POST.get("billable_hours_lost")),
                notes=request.POST.get("notes"),
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Blocker resolved.")

        elif action == "add_limitation":
            ctx.limitation_manager.create_record(
                status=request.POST.get("status", CapabilityStatus.NON_CAPABLE),
                limitation_description=request.POST.get("limitation_description", ""),
                temporary_modifications=request.POST.get("temporary_modifications", ""),
                start_time=_datetime(request.POST.get("start_time")),
                link_to_active_blocker=request.POST.get("link_to_blocker") == "true",
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Asset limitation opened.")

        elif action == "edit_limitation":
            ctx.limitation_manager.update_record(
                record_id=_int(request.POST.get("record_id")),
                status=request.POST.get("status"),
                limitation_description=request.POST.get("limitation_description"),
                temporary_modifications=request.POST.get("temporary_modifications"),
                actor=request.user,
            )
            messages.success(request, "Asset limitation updated.")

        elif action == "close_limitation":
            ctx.limitation_manager.close_record(
                record_id=_int(request.POST.get("record_id")),
                resolution_notes=_required_notes(
                    request,
                    "A resolution note is required to close a limitation.",
                    field="resolution_notes",
                ),
                start_time=_datetime(request.POST.get("start_time")),
                end_time=_datetime(request.POST.get("end_time")),
                comment=request.POST.get("comment", ""),
                actor=request.user,
            )
            messages.success(request, "Asset limitation closed.")

        # ── Per-action parts and tools ─────────────────────────────────────
        elif action == "add_action_part_demand":
            PartDemandManager.create_for_action(
                action_id=_int(request.POST.get("action_id")),
                part_id=_int(request.POST.get("part_id")),
                quantity_requested=_decimal(request.POST.get("quantity")) or Decimal("1"),
                notes=request.POST.get("notes", ""),
                priority=request.POST.get("priority") or None,
                requested_by=request.user,
                actor=request.user,
            )
            messages.success(request, "Part demand added.")

        elif action == "remove_action_part_demand":
            PartDemandManager.remove_link(
                link_id=_int(request.POST.get("link_id")), actor=request.user
            )
            messages.success(request, "Part demand removed.")

        elif action == "add_action_tool":
            ActionToolManager.create_for_action(
                action_id=_int(request.POST.get("action_id")),
                tool_id=_int(request.POST.get("tool_id")) if request.POST.get("tool_id") else None,
                tool_name=request.POST.get("tool_name", "").strip(),
                quantity_required=_int(request.POST.get("quantity_required")) or 1,
                specifications=request.POST.get("specifications", ""),
                notes=request.POST.get("notes", ""),
                actor=request.user,
            )
            messages.success(request, "Tool added.")

        elif action == "edit_action_tool":
            ActionToolManager.update(
                action_tool_id=_int(request.POST.get("action_tool_id")),
                quantity_required=_int(request.POST.get("quantity_required")),
                specifications=request.POST.get("specifications"),
                notes=request.POST.get("notes"),
                actor=request.user,
            )
            messages.success(request, "Tool updated.")

        elif action == "remove_action_tool":
            ActionToolManager.delete(
                action_tool_id=_int(request.POST.get("action_tool_id")), actor=request.user
            )
            messages.success(request, "Tool removed.")

        # ── The five action sources ────────────────────────────────────────
        elif action == "add_blank_action":
            ctx.action_creation_manager.create_blank(
                action_name=request.POST.get("action_name") or "New step",
                description=request.POST.get("description", ""),
                actor=request.user,
            )
            messages.success(request, "Blank step added.")

        elif action == "add_from_proto":
            ctx.action_creation_manager.create_from_proto_action_item(
                proto_action_item_id=_int(request.POST.get("proto_id")),
                actor=request.user,
            )
            messages.success(request, "Step added from proto action.")

        elif action == "add_from_template_action":
            ctx.action_creation_manager.create_from_template_action_item(
                template_action_item_id=_int(request.POST.get("template_action_id")),
                actor=request.user,
            )
            messages.success(request, "Step added from template action.")

        elif action == "add_from_template_set":
            set_id = _int(request.POST.get("template_action_set_id"))
            items = TemplateActionItem.objects.filter(
                template_action_set_id=set_id, deleted_at__isnull=True
            ).order_by("sequence_order")
            for item in items:
                ctx.action_creation_manager.create_from_template_action_item(
                    template_action_item_id=item.pk, actor=request.user
                )
            messages.success(request, f"{items.count()} step(s) added from template.")

        elif action == "duplicate_action":
            ctx.action_creation_manager.duplicate(
                action_id=_int(request.POST.get("action_id")), actor=request.user
            )
            messages.success(request, "Step duplicated.")

        # ── List management ────────────────────────────────────────────────
        elif action == "reorder_action":
            ActionContext(_int(request.POST.get("action_id"))).reorder(
                new_sequence_order=_int(request.POST.get("new_sequence_order")) or 1,
                actor=request.user,
            )
            messages.success(request, "Step moved.")

        elif action == "delete_action":
            from django.utils import timezone

            Action.objects.filter(
                pk=_int(request.POST.get("action_id")), event_detail_id=detail.pk
            ).update(deleted_at=timezone.now(), updated_by=request.user)
            messages.success(request, "Step removed.")

        elif action == "save_action":
            fields = {}
            for name in ("action_name", "description", "instructions",
                         "safety_notes", "completion_notes", "notes"):
                if name in request.POST:
                    fields[name] = request.POST.get(name, "")
            status_raw = request.POST.get("status", "").strip()
            if status_raw:
                fields["status"] = status_raw
            duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
            if duration_raw:
                fields["estimated_duration_minutes"] = _int(duration_raw)
            billable_raw = request.POST.get("billable_hours", "").strip()
            if billable_raw:
                fields["billable_hours"] = float(billable_raw)
            for dt_name in ("scheduled_start_time", "start_time", "end_time"):
                dt_raw = request.POST.get(dt_name, "").strip()
                if dt_raw:
                    fields[dt_name] = parse_datetime(dt_raw)
            action_ctx = ActionContext(_int(request.POST.get("action_id")))
            # Sequence order goes through reorder() rather than edit()'s raw
            # field assignment — reorder() shifts sibling actions to keep
            # sequence_order dense and unique, which a bare int field here
            # would silently break (two actions sharing #1, a gap where #2
            # used to be, etc).
            sequence_raw = request.POST.get("sequence_order", "").strip()
            if sequence_raw and _int(sequence_raw) != action_ctx.action.sequence_order:
                action_ctx.reorder(new_sequence_order=_int(sequence_raw), actor=request.user)
            action_ctx.edit(actor=request.user, **fields)
            messages.success(request, "Step saved.")

        else:
            messages.error(request, "Unknown action.")

    except (ValueError, TypeError) as exc:
        messages.error(request, str(exc))

    selected = request.POST.get("action_id", "")
    return redirect(f"{target}?selected={selected}" if selected else target)


#: Action Creator Portal tabs. The same five sources appear in the event edit
#: portal and the template builder; only the POST target differs, so the tab
#: bodies are one partial parameterised by `creator_url`.
CREATOR_TABS = (
    ("template_set", "From Template"),
    ("template_action", "From Template Action"),
    ("proto", "From Proto Action"),
    ("current", "From Current Build"),
    ("blank", "Blank Action"),
)


#: Unfiltered (no `q` typed) listings are capped tight — just enough to show
#: the portal isn't empty and nudge toward the asset-scoped default, not a
#: full browse (that's what typing into the search box is for).
_CREATOR_DEFAULT_LIMIT = 2
_CREATOR_SEARCH_LIMIT = 25


def _creator_tab_context(request: HttpRequest, detail: MaintenanceDetail, *, tab: str, q: str) -> dict:
    """The data for one Action Creator Portal tab body. Shared by the full
    page GET (so the initially-active tab isn't empty on first load — a
    regression the legacy page didn't have, since it always rendered
    `template_set` server-side) and the htmx tab-switch fragment."""
    domain_ids = accessible_domain_ids(request)
    context: dict = {}
    asset_model_id = detail.asset.model_id if detail.asset_id else None

    if tab == "template_set":
        qs = TemplateActionSet.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True, is_active=True
        ).annotate(action_count=Count("template_action_items")).prefetch_related(
            "template_action_items"
        )
        if q:
            qs = qs.filter(Q(task_name__icontains=q) | Q(description__icontains=q))
            context["template_sets"] = qs.order_by("task_name")[:_CREATOR_SEARCH_LIMIT]
        else:
            scoped = qs
            if asset_model_id:
                scoped = qs.filter(
                    Q(asset_models=asset_model_id) | Q(asset_class_id=detail.asset.asset_class_id)
                ).distinct()
            rows = list(scoped.order_by("task_name")[:_CREATOR_DEFAULT_LIMIT])
            context["template_sets"] = rows
            context["template_sets_asset_scoped"] = bool(asset_model_id) and bool(rows)

    elif tab == "template_action":
        qs = TemplateActionItem.objects.filter(
            template_action_set__domain_id__in=domain_ids, deleted_at__isnull=True
        ).select_related("template_action_set")
        if q:
            qs = qs.filter(Q(action_name__icontains=q) | Q(description__icontains=q))
            context["template_actions"] = qs.order_by("action_name")[:_CREATOR_SEARCH_LIMIT]
        else:
            scoped = qs
            if asset_model_id:
                scoped = qs.filter(
                    Q(template_action_set__asset_models=asset_model_id)
                    | Q(template_action_set__asset_class_id=detail.asset.asset_class_id)
                ).distinct()
            context["template_actions"] = scoped.order_by("action_name")[:_CREATOR_DEFAULT_LIMIT]

    elif tab == "proto":
        qs = ProtoActionItem.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True
        )
        if q:
            qs = qs.filter(
                Q(action_name__icontains=q)
                | Q(description__icontains=q)
                | Q(instructions__icontains=q)
            )
            context["proto_actions"] = qs.order_by("action_name")[:_CREATOR_SEARCH_LIMIT]
        else:
            context["proto_actions"] = qs.order_by("action_name")[:_CREATOR_DEFAULT_LIMIT]

    elif tab == "current":
        context["current_actions"] = detail.actions.filter(
            deleted_at__isnull=True
        ).order_by("sequence_order")

    return context


def _action_creator_fragment(request: HttpRequest, detail: MaintenanceDetail) -> HttpResponse:
    """One canonical URL branching on `format=`, per the format= contract —
    not five fragment-only routes."""
    tab = request.GET.get("tab", "template_set")
    q = request.GET.get("q", "").strip()

    context = {
        "tab": tab,
        "q": q,
        "tabs": CREATOR_TABS,
        "creator_url": reverse("maintenance_edit", kwargs={"pk": detail.pk}),
        "detail": detail,
    }
    context.update(_creator_tab_context(request, detail, tab=tab, q=q))
    return render(request, "maintenance/work/_action_creator.html", context)


def _action_editor_panel_fragment(request: HttpRequest, detail: MaintenanceDetail) -> HttpResponse:
    """Render just the action editor panel for HTMX updates.

    Used when switching between actions to avoid full page reload."""
    struct = MaintenanceDetailStruct.load(maintenance_detail_id=detail.pk)
    actions = _attach_children(struct.actions)
    selected_id = _int(request.GET.get("selected"))
    selected = next((a for a in actions if a.pk == selected_id), None)

    if selected is None and actions:
        selected = actions[0]

    context = {
        "detail": detail,
        "actions": actions,
        "selected_action": selected,
        "action_statuses": ActionStatus.choices,
        "demand_priorities": DemandPriority.choices,
        "tools_catalog": Tool.objects.filter(is_active=True).order_by("name"),
        "parts_catalog": Part.objects.order_by("part_number"),
    }

    return render(request, "maintenance/work/_action_editor_panel.html", context)


# --------------------------------------------------------------------------- #
# Assign
# --------------------------------------------------------------------------- #


@require_http_methods(["GET", "POST"])
def maintenance_assign(request: HttpRequest, pk: int) -> HttpResponse:
    """Single-event (re)assign (legacy /maintenance-event/<id>/assign).

    The technician picker shows each candidate's current open workload, which
    is what makes this an assignment tool rather than a dropdown.
    """
    detail = _detail_or_404(request, pk)

    if request.method == "POST":
        user_id = _int(request.POST.get("assigned_user_id"))
        if not user_id:
            messages.error(request, "Choose a technician.")
            return redirect(reverse("maintenance_assign", kwargs={"pk": pk}))
        user = get_object_or_404(User, pk=user_id)
        MaintenanceContext(pk).assignment_manager.assign(
            assigned_user=user, assigned_by=request.user
        )
        messages.success(request, f"Assigned to {user}.")
        return redirect(reverse("maintenance_detail", kwargs={"pk": pk}))

    if request.GET.get("format") == "htmx-technicians":
        return render(
            request,
            "maintenance/work/_technician_results.html",
            {"technicians": technician_pool(request, q=request.GET.get("q", ""))},
        )

    return render(
        request,
        "maintenance/work/assign.html",
        {"detail": detail, "technicians": technician_pool(request)},
    )


def technician_pool(request: HttpRequest, *, q: str = "", limit: int = 25):
    """Candidate assignees annotated with their current open workload.

    Shared by the assign page, the create-&-assign portal, and the bulk-assign
    card, so "0 active" means the same number everywhere.
    """
    domain_ids = accessible_domain_ids(request)
    qs = User.objects.filter(is_active=True)
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    return qs.annotate(
        active_count=Count(
            "assigned_maintenance_events",
            filter=Q(
                assigned_maintenance_events__deleted_at__isnull=True,
                assigned_maintenance_events__domain_id__in=domain_ids,
            )
            & ~Q(assigned_maintenance_events__status__in=["completed", "cancelled"]),
            distinct=True,
        )
    ).order_by("username")[:limit]
