"""Presentation-layer entrypoints for Dispatch records (index, create, detail, edit, and actions)."""

from __future__ import annotations

import calendar as _calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, models
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app.administration.models import Domain
from app.assets.models import AssetClass
from app.dispatching.control_layer.dispatch_context import DispatchContext
from app.dispatching.control_layer.domain_structs.dispatch_cost_struct import DispatchCostStruct
from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.control_layer.factories.dispatch_from_template_factory import (
    DispatchFromTemplateFactory,
)
from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.managers.reservation_promotion_manager import (
    ReservationPromotionManager,
)
from app.dispatching.models.enums import ExpenseType, PersonnelRole
from app.dispatching.models.templates.dispatch_template_revision import (
    DispatchTemplateRevision,
)
from app.dispatching.presentation_layer.search import reservation_search as rs
from app.dispatching.presentation_layer.tools.dispatching_access import (
    accessible_domain_ids,
    can_complete_dispatch,
    can_plan_dispatch,
    can_raise_dispatch,
    can_read_dispatching,
    can_reject_dispatch,
    can_view_dispatches,
    is_in_domain,
)
from app.events.models.details.dispatching import (
    DispatchingDetail,
    DispatchScope,
    DispatchWorkflowStatus,
    RejectionCategory,
)
from app.dispatching.models.line_items.dispatch_personnel import DispatchPersonnel
from app.dispatching.models.skills.user_dispatch_skill import UserDispatchSkill
from app.events.presentation_layer.tools.generic_cards import build_activity_card
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.control_layer.errors import TransitionRefused

User = get_user_model()


@dataclass
class DispatchCalendarDay:
    day: date
    in_month: bool
    is_today: bool
    dispatches: list[DispatchingDetail] = field(default_factory=list)


def build_dispatch_month_grid(
    *, dispatches: list[DispatchingDetail], anchor: date
) -> list[list[DispatchCalendarDay]]:
    today = timezone.localdate()
    weeks = _calendar.Calendar(firstweekday=6).monthdatescalendar(anchor.year, anchor.month)

    spans: list[tuple[date, date, DispatchingDetail]] = []
    for d in dispatches:
        start_dt = d.desired_start or d.created_at or timezone.now()
        end_dt = d.desired_end or (start_dt + timedelta(hours=8))
        spans.append(
            (
                timezone.localtime(start_dt).date(),
                timezone.localtime(end_dt).date(),
                d,
            )
        )

    grid: list[list[DispatchCalendarDay]] = []
    for week in weeks:
        row: list[DispatchCalendarDay] = []
        for day in week:
            row.append(
                DispatchCalendarDay(
                    day=day,
                    in_month=(day.month == anchor.month),
                    is_today=(day == today),
                    dispatches=[d for start, end, d in spans if start <= day <= end],
                )
            )
        grid.append(row)
    return grid


@login_required
def dispatch_index(request: HttpRequest) -> HttpResponse:
    if not can_view_dispatches(request):
        raise PermissionDenied("You do not have permission to view dispatches.")

    domain_ids = accessible_domain_ids(request)
    base_qs = DispatchingDetail.objects.filter(deleted_at__isnull=True, domain_id__in=domain_ids).select_related(
        "requested_for", "requested_by", "asset_class", "domain"
    )

    # Data fencing: non-dispatchers only see dispatches they requested/raised
    if not (can_plan_dispatch(request) or can_read_dispatching(request)):
        base_qs = base_qs.filter(requested_for_id=request.user.pk)

    raw_start = request.GET.get("start")
    raw_end = request.GET.get("end")

    window_start = rs.parse_date(raw_start)
    window_end = rs.parse_date(raw_end)

    if window_start is None or window_end is None:
        window_start, window_end = rs.default_window()

    month_anchor = window_start.replace(day=1)
    previous_window = rs.month_bounds(rs.shift_month(month_anchor, -1))
    this_window = rs.default_window()
    next_window = rs.month_bounds(rs.shift_month(month_anchor, 1))

    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    asset_class_id = request.GET.get("asset_class", "").strip()
    dispatch_scope = request.GET.get("dispatch_scope", "").strip()
    domain_id = request.GET.get("domain", "").strip()
    requested_for_id = (
        request.GET.get("requested_for") or request.GET.get("requested-for") or ""
    ).strip()
    has_assigned_person_id = (
        request.GET.get("has_assigned_person") or request.GET.get("has-assigned-person") or ""
    ).strip()
    mine_only = request.GET.get("mine") == "1"

    start_dt, end_dt = rs.as_aware_range(window_start, window_end)
    qs = base_qs.filter(desired_start__lt=end_dt, desired_end__gte=start_dt)

    if q:
        qs = qs.filter(
            models.Q(title__icontains=q)
            | models.Q(description__icontains=q)
            | models.Q(activity_location__icontains=q)
            | models.Q(requested_assets__icontains=q)
            | models.Q(asset_subclass_text__icontains=q)
        )
    if status_filter:
        qs = qs.filter(workflow_status=status_filter)
    if asset_class_id:
        qs = qs.filter(asset_class_id=asset_class_id)
    if dispatch_scope:
        qs = qs.filter(dispatch_scope=dispatch_scope)
    if domain_id:
        qs = qs.filter(domain_id=domain_id)

    if requested_for_id and has_assigned_person_id:
        qs = qs.filter(
            models.Q(requested_for_id=requested_for_id)
            | models.Q(crew__user_id=has_assigned_person_id)
        ).distinct()
    elif requested_for_id:
        qs = qs.filter(requested_for_id=requested_for_id)
    elif has_assigned_person_id:
        qs = qs.filter(crew__user_id=has_assigned_person_id).distinct()
    elif mine_only:
        qs = qs.filter(
            models.Q(requested_for_id=request.user.pk)
            | models.Q(crew__user_id=request.user.pk)
        ).distinct()

    dispatches_list = list(qs.order_by("desired_start", "pk"))
    weeks = build_dispatch_month_grid(dispatches=dispatches_list, anchor=month_anchor)

    # Base querystring without start/end for prev/next month buttons
    qd = request.GET.copy()
    qd.pop("start", None)
    qd.pop("end", None)
    querystring_base = qd.urlencode()
    if querystring_base:
        querystring_base += "&"

    summary = {
        "total": base_qs.count(),
        "requested": base_qs.filter(workflow_status=DispatchWorkflowStatus.REQUESTED).count(),
        "under_review": base_qs.filter(workflow_status=DispatchWorkflowStatus.UNDER_REVIEW).count(),
        "fixes_requested": base_qs.filter(workflow_status=DispatchWorkflowStatus.FIXES_REQUESTED).count(),
        "planned": base_qs.filter(workflow_status=DispatchWorkflowStatus.PLANNED).count(),
        "alternate": base_qs.filter(workflow_status=DispatchWorkflowStatus.ALTERNATE_RESOLUTION).count(),
        "completed": base_qs.filter(workflow_status=DispatchWorkflowStatus.COMPLETED).count(),
        "rejected_cancelled": base_qs.filter(
            workflow_status__in=[DispatchWorkflowStatus.REJECTED, DispatchWorkflowStatus.CANCELLED]
        ).count(),
    }

    domains = Domain.objects.filter(pk__in=domain_ids)
    asset_classes = AssetClass.objects.all()
    people = User.objects.filter(is_active=True).order_by("first_name", "last_name")

    context = {
        "dispatches": dispatches_list,
        "weeks": weeks,
        "month_anchor": month_anchor,
        "window_start": window_start,
        "window_end": window_end,
        "previous_window": previous_window,
        "this_window": this_window,
        "next_window": next_window,
        "querystring_base": querystring_base,
        "summary": summary,
        "statuses": DispatchWorkflowStatus.choices,
        "dispatch_scopes": DispatchScope.choices,
        "asset_classes": asset_classes,
        "domains": domains,
        "people": people,
        "q": q,
        "status": status_filter,
        "asset_class": asset_class_id,
        "dispatch_scope": dispatch_scope,
        "domain": domain_id,
        "requested_for": requested_for_id,
        "mine_only": mine_only,
        "can_raise": can_raise_dispatch(request),
    }
    return render(request, "dispatching/dispatches/index.html", context)


import uuid
from django.db import IntegrityError, models, transaction

DISPATCH_CREATE_SESSION_KEY = "dispatch_create_draft"
_REQUIREMENT_KINDS = ("capability", "skill", "model", "modification")


def _blank_dispatch_create_draft() -> dict:
    return {
        "template_id": None,
        "revision_id": None,
        "domain_id": None,
        "requested_for_id": None,
        "desired_start": "",
        "desired_end": "",
        "title": "",
        "asset_class_id": None,
        "asset_subclass_text": "",
        "dispatch_scope": "",
        "activity_location": "",
        "estimated_meter_usage": None,
        "headcount": None,
        "description": "",
        "requested_assets": "",
        "names_free_text": "",
        "requirements": {kind: [] for kind in _REQUIREMENT_KINDS},
        "material_requirements": [],
        "personnel": [],
    }


def _resolve_requirement_rows(draft: dict) -> dict:
    from app.assets.models import AssetModel, CapabilityDefinition, ConfigurationTemplate, DefinedModification
    from app.dispatching.models.skills.dispatch_skill import DispatchSkill

    lookups = {
        "capability": (CapabilityDefinition.objects, "capability_definition_id"),
        "skill": (DispatchSkill.objects, "skill_id"),
        "model": (
            AssetModel.objects.select_related("asset_class").prefetch_related("manufacturers"),
            "model_id",
        ),
        "modification": (DefinedModification.objects, "defined_modification_id"),
    }
    out: dict = {}
    for kind, (queryset, id_field) in lookups.items():
        rows = draft.get("requirements", {}).get(kind, [])
        ids = [r[id_field] for r in rows if id_field in r]
        objects_by_id = {obj.pk: obj for obj in queryset.filter(pk__in=ids)}
        out[kind] = [
            {**row, "object": objects_by_id.get(row[id_field])} for row in rows if id_field in row
        ]

    config_ids = [r["configuration_template_id"] for r in out.get("model", []) if r.get("configuration_template_id")]
    configs_by_id = {c.pk: c for c in ConfigurationTemplate.objects.filter(pk__in=config_ids)}
    out["model"] = [
        {**row, "configuration_template": configs_by_id.get(row.get("configuration_template_id"))}
        for row in out.get("model", [])
    ]
    return out


def _resolve_material_rows(draft: dict) -> list[dict]:
    from app.parts.models import Part

    rows = draft.get("material_requirements", [])
    parts_by_id = {p.pk: p for p in Part.objects.filter(pk__in=[r["part_id"] for r in rows if "part_id" in r])}
    return [{**row, "part": parts_by_id.get(row["part_id"])} for row in rows if "part_id" in row]


def _resolve_personnel_rows(draft: dict) -> list[dict]:
    from app.administration.models import User
    from app.dispatching.models.enums import PersonnelRole

    rows = draft.get("personnel", [])
    users_by_id = {u.pk: u for u in User.objects.filter(pk__in=[r["user_id"] for r in rows if "user_id" in r])}
    role_labels = dict(PersonnelRole.choices)
    return [
        {
            **row,
            "user": users_by_id.get(row["user_id"]),
            "role_display": role_labels.get(row.get("role"), row.get("role")),
        }
        for row in rows
        if "user_id" in row
    ]


@login_required
def dispatch_create(request: HttpRequest) -> HttpResponse:
    if not can_raise_dispatch(request):
        raise PermissionDenied("You do not have permission to create a dispatch.")

    domain_ids = accessible_domain_ids(request)
    template_param = request.GET.get("template")

    draft = request.session.get(DISPATCH_CREATE_SESSION_KEY)
    template_rev = None

    if template_param:
        template_rev = (
            DispatchTemplateRevision.objects.filter(
                models.Q(pk=template_param) | models.Q(template_id=template_param),
                template__domain_id__in=domain_ids,
            )
            .select_related("template")
            .order_by("-revision_number")
            .first()
        )

        if template_rev and (not draft or draft.get("revision_id") != template_rev.pk):
            draft = _blank_dispatch_create_draft()
            draft["template_id"] = template_rev.template_id
            draft["revision_id"] = template_rev.pk
            draft["domain_id"] = template_rev.template.domain_id
            draft["title"] = template_rev.title
            draft["asset_class_id"] = template_rev.asset_class_id
            draft["asset_subclass_text"] = template_rev.asset_subclass_text or ""
            draft["dispatch_scope"] = template_rev.dispatch_scope or ""
            draft["activity_location"] = template_rev.activity_location or ""
            draft["estimated_meter_usage"] = template_rev.estimated_meter_usage
            draft["headcount"] = template_rev.headcount
            draft["description"] = template_rev.notes or ""

            for cap in template_rev.requested_capabilities.all():
                draft["requirements"]["capability"].append({
                    "temp_id": uuid.uuid4().hex,
                    "capability_definition_id": cap.capability_definition_id,
                    "is_required": cap.is_required,
                    "notes": cap.notes or "",
                })
            for sk in template_rev.requested_skills.all():
                draft["requirements"]["skill"].append({
                    "temp_id": uuid.uuid4().hex,
                    "skill_id": sk.skill_id,
                    "quantity": sk.quantity,
                    "minimum_level": sk.minimum_level,
                    "is_required": sk.is_required,
                    "notes": sk.notes or "",
                })
            for mod in template_rev.requested_modifications.all():
                draft["requirements"]["modification"].append({
                    "temp_id": uuid.uuid4().hex,
                    "defined_modification_id": mod.defined_modification_id,
                    "is_required": mod.is_required,
                    "notes": mod.notes or "",
                })
            for mreq in template_rev.requested_models.all():
                draft["requirements"]["model"].append({
                    "temp_id": uuid.uuid4().hex,
                    "model_id": mreq.model_id,
                    "configuration_template_id": mreq.configuration_template_id,
                    "quantity": mreq.quantity,
                    "is_required": mreq.is_required,
                    "notes": mreq.notes or "",
                })
            for mat in template_rev.material_requirements.all():
                draft["material_requirements"].append({
                    "temp_id": uuid.uuid4().hex,
                    "part_id": mat.part_id,
                    "quantity": float(mat.quantity),
                    "notes": mat.notes or "",
                })

            request.session[DISPATCH_CREATE_SESSION_KEY] = draft
            request.session.modified = True
    elif not draft:
        draft = _blank_dispatch_create_draft()
        request.session[DISPATCH_CREATE_SESSION_KEY] = draft
        request.session.modified = True

    if draft and draft.get("revision_id") and not template_rev:
        template_rev = (
            DispatchTemplateRevision.objects.filter(pk=draft["revision_id"])
            .select_related("template")
            .first()
        )

    if request.method == "POST":
        action = request.POST.get("action", "")

        domain_id_post = request.POST.get("domain_id")
        if domain_id_post and domain_id_post.isdigit():
            draft["domain_id"] = int(domain_id_post)
        req_for_post = request.POST.get("requested_for_id")
        if req_for_post and req_for_post.isdigit():
            draft["requested_for_id"] = int(req_for_post)
        if "title" in request.POST:
            draft["title"] = request.POST.get("title", "").strip()
        ac_id_post = request.POST.get("asset_class_id")
        if ac_id_post and ac_id_post.isdigit():
            draft["asset_class_id"] = int(ac_id_post)
        if "asset_subclass_text" in request.POST:
            draft["asset_subclass_text"] = request.POST.get("asset_subclass_text", "").strip()
        if "desired_start" in request.POST:
            draft["desired_start"] = request.POST.get("desired_start", "")
        if "desired_end" in request.POST:
            draft["desired_end"] = request.POST.get("desired_end", "")
        if "dispatch_scope" in request.POST:
            draft["dispatch_scope"] = request.POST.get("dispatch_scope", "")
        hc_post = request.POST.get("headcount", "").strip()
        if hc_post:
            draft["headcount"] = int(hc_post) if hc_post.isdigit() else None
        m_post = request.POST.get("estimated_meter_usage", "").strip()
        if m_post:
            try:
                draft["estimated_meter_usage"] = float(m_post)
            except ValueError:
                pass
        if "activity_location" in request.POST:
            draft["activity_location"] = request.POST.get("activity_location", "").strip()
        if "requested_assets" in request.POST:
            draft["requested_assets"] = request.POST.get("requested_assets", "").strip()
        if "names_free_text" in request.POST:
            draft["names_free_text"] = request.POST.get("names_free_text", "").strip()
        if "description" in request.POST:
            draft["description"] = request.POST.get("description", "").strip()
        request.session.modified = True

        redirect_url = request.path
        if template_param:
            redirect_url += f"?template={template_param}"

        try:
            if action == "add_requirement":
                kind = request.POST.get("kind", "")
                fields: dict = {
                    "is_required": request.POST.get("is_required") == "on",
                    "notes": request.POST.get("notes", "").strip(),
                }
                id_field = {
                    "capability": "capability_definition_id",
                    "skill": "skill_id",
                    "model": "model_id",
                    "modification": "defined_modification_id",
                }.get(kind)
                picked_id_raw = request.POST.get("picked_id", "").strip()
                if id_field is None or not picked_id_raw.isdigit():
                    raise ValueError("Pick a value before adding a requirement.")
                fields[id_field] = int(picked_id_raw)
                if kind in ("skill", "model"):
                    qty_raw = request.POST.get("quantity", "1").strip()
                    fields["quantity"] = int(qty_raw) if qty_raw.isdigit() else 1
                if kind == "skill":
                    level_raw = request.POST.get("minimum_level", "").strip()
                    fields["minimum_level"] = int(level_raw) if level_raw.isdigit() else None
                if kind == "model":
                    config_id_raw = request.POST.get("configuration_template_id", "").strip()
                    if config_id_raw.isdigit():
                        from app.assets.models import ConfigurationTemplate
                        config = ConfigurationTemplate.objects.filter(pk=int(config_id_raw)).first()
                        if config is None or config.model_id != fields["model_id"]:
                            raise ValueError("That configuration does not belong to the picked model.")
                        fields["configuration_template_id"] = config.pk

                row = {"temp_id": uuid.uuid4().hex, **fields}
                draft["requirements"][kind].append(row)
                request.session.modified = True
                return redirect(redirect_url)

            elif action == "remove_requirement":
                kind = request.POST.get("kind", "")
                temp_id = request.POST.get("temp_id", "")
                if kind in draft["requirements"]:
                    draft["requirements"][kind] = [r for r in draft["requirements"][kind] if r.get("temp_id") != temp_id]
                    request.session.modified = True
                return redirect(redirect_url)

            elif action == "add_material_requirement":
                part_id_raw = request.POST.get("part_id", "").strip()
                qty_raw = request.POST.get("quantity", "").strip()
                if not part_id_raw.isdigit() or not qty_raw:
                    raise ValueError("Pick a part and a quantity before adding a material requirement.")
                row = {
                    "temp_id": uuid.uuid4().hex,
                    "part_id": int(part_id_raw),
                    "quantity": float(qty_raw),
                    "notes": request.POST.get("notes", "").strip(),
                }
                draft["material_requirements"].append(row)
                request.session.modified = True
                return redirect(redirect_url)

            elif action == "remove_material_requirement":
                temp_id = request.POST.get("temp_id", "")
                draft["material_requirements"] = [m for m in draft["material_requirements"] if m.get("temp_id") != temp_id]
                request.session.modified = True
                return redirect(redirect_url)

            elif action == "add_personnel":
                user_id_raw = request.POST.get("user_id", "").strip()
                if not user_id_raw.isdigit():
                    raise ValueError("Select a user before assigning personnel.")
                role = request.POST.get("role", PersonnelRole.PASSENGER)
                notes = request.POST.get("notes", "").strip()
                row = {
                    "temp_id": uuid.uuid4().hex,
                    "user_id": int(user_id_raw),
                    "role": role,
                    "notes": notes,
                }
                draft.setdefault("personnel", []).append(row)
                request.session.modified = True
                return redirect(redirect_url)

            elif action == "remove_personnel":
                temp_id = request.POST.get("temp_id", "")
                draft["personnel"] = [p for p in draft.get("personnel", []) if p.get("temp_id") != temp_id]
                request.session.modified = True
                return redirect(redirect_url)

            elif action == "clear_template":
                request.session.pop(DISPATCH_CREATE_SESSION_KEY, None)
                return redirect("dispatching_dispatch_create")

            else:
                domain_id = int(request.POST.get("domain_id") or draft.get("domain_id") or domain_ids[0])
                requested_for_id = int(request.POST.get("requested_for_id") or draft.get("requested_for_id") or request.user.pk)
                desired_start = request.POST.get("desired_start") or draft.get("desired_start")
                desired_end = request.POST.get("desired_end") or draft.get("desired_end")
                title = request.POST.get("title", "").strip() or draft.get("title", "")
                asset_class_id_raw = request.POST.get("asset_class_id") or draft.get("asset_class_id")
                asset_class_id = int(asset_class_id_raw) if asset_class_id_raw else 0
                description = request.POST.get("description", "").strip() or draft.get("description", "")
                activity_location = request.POST.get("activity_location", "").strip() or draft.get("activity_location", "")
                created_from_revision_id = draft.get("revision_id") or (template_rev.pk if template_rev else None)

                if not asset_class_id:
                    raise ValueError("Asset Class is required.")
                if not desired_start or not desired_end:
                    raise ValueError("Desired Start and Desired End are required.")
                if not title:
                    raise ValueError("Title is required.")

                with transaction.atomic():
                    dispatch = DispatchFactory.create(
                        domain_id=domain_id,
                        requested_for_id=requested_for_id,
                        desired_start=desired_start,
                        desired_end=desired_end,
                        asset_class_id=asset_class_id,
                        requested_by_id=request.user.pk,
                        asset_subclass_text=request.POST.get("asset_subclass_text", "").strip() or draft.get("asset_subclass_text", ""),
                        headcount=int(request.POST.get("headcount")) if request.POST.get("headcount", "").isdigit() else draft.get("headcount"),
                        names_free_text=request.POST.get("names_free_text", "").strip() or draft.get("names_free_text", ""),
                        requested_assets=request.POST.get("requested_assets", "").strip() or draft.get("requested_assets", ""),
                        dispatch_scope=request.POST.get("dispatch_scope", "") or draft.get("dispatch_scope", ""),
                        estimated_meter_usage=float(request.POST.get("estimated_meter_usage")) if request.POST.get("estimated_meter_usage", "").strip() else draft.get("estimated_meter_usage"),
                        activity_location=activity_location or None,
                        title=title,
                        description=description,
                        created_from_revision_id=created_from_revision_id,
                        actor=request.user,
                    )

                    ctx = DispatchContext(dispatch.pk, request.user)

                    for req in draft.get("requirements", {}).get("capability", []):
                        ctx.requirements.add(
                            kind="capability",
                            target_id=req["capability_definition_id"],
                            is_required=req.get("is_required", True),
                            notes=req.get("notes", ""),
                            actor=request.user,
                        )
                    for req in draft.get("requirements", {}).get("skill", []):
                        ctx.requirements.add(
                            kind="skill",
                            target_id=req["skill_id"],
                            is_required=req.get("is_required", True),
                            notes=req.get("notes", ""),
                            quantity=req.get("quantity", 1),
                            minimum_level=req.get("minimum_level"),
                            actor=request.user,
                        )
                    for req in draft.get("requirements", {}).get("modification", []):
                        ctx.requirements.add(
                            kind="modification",
                            target_id=req["defined_modification_id"],
                            is_required=req.get("is_required", True),
                            notes=req.get("notes", ""),
                            actor=request.user,
                        )
                    for req in draft.get("requirements", {}).get("model", []):
                        ctx.requirements.add(
                            kind="model",
                            target_id=req["model_id"],
                            is_required=req.get("is_required", True),
                            notes=req.get("notes", ""),
                            quantity=req.get("quantity", 1),
                            configuration_template_id=req.get("configuration_template_id"),
                            actor=request.user,
                        )
                    for mat in draft.get("material_requirements", []):
                        ctx.demands.raise_demand(
                            part_id=mat["part_id"],
                            quantity_requested=mat["quantity"],
                            notes=mat.get("notes", ""),
                            actor=request.user,
                        )

                    from app.dispatching.models.line_items.dispatch_personnel import DispatchPersonnel
                    for p in draft.get("personnel", []):
                        DispatchPersonnel.objects.create(
                            dispatch=dispatch,
                            user_id=p["user_id"],
                            role=p.get("role", PersonnelRole.PASSENGER),
                            notes=p.get("notes", ""),
                            created_by=request.user,
                            updated_by=request.user,
                        )

                request.session.pop(DISPATCH_CREATE_SESSION_KEY, None)
                messages.success(request, f"Dispatch #{dispatch.pk} ('{dispatch.title}') raised in Requested status.")
                return redirect("dispatching_dispatch_edit", pk=dispatch.pk)

        except (ValueError, KeyError, IntegrityError) as exc:
            messages.error(request, str(exc))

    domains = Domain.objects.filter(pk__in=domain_ids)
    asset_classes = AssetClass.objects.all()
    users = User.objects.filter(is_active=True).order_by("first_name", "last_name")

    context = {
        "draft": draft,
        "template_rev": template_rev,
        "requirement_rows": _resolve_requirement_rows(draft),
        "material_rows": _resolve_material_rows(draft),
        "personnel_rows": _resolve_personnel_rows(draft),
        "personnel_roles": PersonnelRole.choices,
        "domains": domains,
        "asset_classes": asset_classes,
        "users": users,
        "dispatch_scope_choices": DispatchScope.choices,
    }
    return render(request, "dispatching/dispatches/create.html", context)


@login_required
def dispatch_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_view_dispatches(request):
        raise PermissionDenied("You do not have permission to view dispatches.")

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    if not is_in_domain(request, ctx.dispatch.domain_id):
        raise Http404("Dispatch not found in active domain.")

    costs = DispatchCostStruct.load(dispatch_id=pk)
    activity = build_activity_card(ctx.dispatch, request.user)
    intent_editable = IntentLockPolicy.is_fully_editable(ctx.dispatch)

    context = {
        "dispatch": ctx.dispatch,
        "struct": ctx.struct,
        "costs": costs,
        "activity": activity,
        "intent_editable": intent_editable,
        "rejection_categories": RejectionCategory.choices,
        "can_raise": can_raise_dispatch(request),
        "can_plan": can_plan_dispatch(request),
        "can_reject": can_reject_dispatch(request),
        "can_complete": can_complete_dispatch(request),
    }
    return render(request, "dispatching/dispatches/detail.html", context)


def _get_available_personnel_context(
    dispatch: DispatchingDetail,
    username_q: str = "",
    skill_q: str = "",
    include_overlapping: bool = False,
) -> tuple[list[User], set[int]]:
    qs = User.objects.filter(is_active=True)

    assigned_user_ids = set(
        DispatchPersonnel.objects.filter(dispatch_id=dispatch.pk).values_list("user_id", flat=True)
    )
    qs = qs.exclude(pk__in=assigned_user_ids)

    overlapping_user_ids: set[int] = set()
    if dispatch.desired_start and dispatch.desired_end:
        overlapping_dispatches = DispatchingDetail.objects.filter(
            desired_start__lt=dispatch.desired_end,
            desired_end__gte=dispatch.desired_start,
        ).exclude(pk=dispatch.pk).exclude(workflow_status=DispatchWorkflowStatus.CANCELLED)

        overlapping_user_ids = set(
            DispatchPersonnel.objects.filter(dispatch__in=overlapping_dispatches).values_list("user_id", flat=True)
        )

    if not include_overlapping and overlapping_user_ids:
        qs = qs.exclude(pk__in=overlapping_user_ids)

    if username_q:
        qs = qs.filter(
            models.Q(username__icontains=username_q)
            | models.Q(first_name__icontains=username_q)
            | models.Q(last_name__icontains=username_q)
            | models.Q(email__icontains=username_q)
        )

    if skill_q:
        qs = qs.filter(
            dispatch_skills__skill__name__icontains=skill_q,
            dispatch_skills__is_active=True,
        )

    available_users = list(
        qs.prefetch_related(
            models.Prefetch(
                "dispatch_skills",
                queryset=UserDispatchSkill.objects.filter(is_active=True).select_related("skill"),
                to_attr="active_skills_list",
            )
        ).order_by("username").distinct()
    )

    return available_users, overlapping_user_ids


@login_required
def dispatch_personnel_search(request: HttpRequest, pk: int) -> HttpResponse:
    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    if not is_in_domain(request, ctx.dispatch.domain_id):
        raise Http404("Dispatch not found in active domain.")

    username_q = request.GET.get("user_name", "").strip()
    skill_q = request.GET.get("skill_name", "").strip()
    include_overlapping = request.GET.get("include_overlapping") in ("on", "true", "1")

    available_users, overlapping_user_ids = _get_available_personnel_context(
        ctx.dispatch,
        username_q=username_q,
        skill_q=skill_q,
        include_overlapping=include_overlapping,
    )

    context = {
        "dispatch": ctx.dispatch,
        "available_users": available_users,
        "overlapping_user_ids": overlapping_user_ids,
        "username_q": username_q,
        "skill_q": skill_q,
        "include_overlapping": include_overlapping,
        "personnel_roles": PersonnelRole.choices,
    }
    return render(request, "dispatching/dispatches/_available_personnel.html", context)


@login_required
def dispatch_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not (can_raise_dispatch(request) or can_plan_dispatch(request)):
        raise PermissionDenied("You do not have permission to edit dispatches.")

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    if not is_in_domain(request, ctx.dispatch.domain_id):
        raise Http404("Dispatch not found in active domain.")

    costs = DispatchCostStruct.load(dispatch_id=pk)
    intent_locked = not IntentLockPolicy.is_fully_editable(ctx.dispatch)

    domain_ids = accessible_domain_ids(request)
    domains = Domain.objects.filter(pk__in=domain_ids)
    asset_classes = AssetClass.objects.all()
    users = User.objects.filter(is_active=True).order_by("first_name", "last_name")

    username_q = request.GET.get("user_name", "").strip()
    skill_q = request.GET.get("skill_name", "").strip()
    include_overlapping = request.GET.get("include_overlapping") in ("on", "true", "1")

    available_users, overlapping_user_ids = _get_available_personnel_context(
        ctx.dispatch,
        username_q=username_q,
        skill_q=skill_q,
        include_overlapping=include_overlapping,
    )

    context = {
        "dispatch": ctx.dispatch,
        "struct": ctx.struct,
        "costs": costs,
        "intent_locked": intent_locked,
        "domains": domains,
        "asset_classes": asset_classes,
        "users": users,
        "available_users": available_users,
        "overlapping_user_ids": overlapping_user_ids,
        "username_q": username_q,
        "skill_q": skill_q,
        "include_overlapping": include_overlapping,
        "personnel_roles": PersonnelRole.choices,
        "expense_types": ExpenseType.choices,
        "can_plan": can_plan_dispatch(request),
        "can_raise": can_raise_dispatch(request),
    }
    return render(request, "dispatching/dispatches/edit.html", context)


# ─────────────────────────────────────────────────────────────────────────
# Action Handlers (POST only)
# ─────────────────────────────────────────────────────────────────────────

@login_required
def dispatch_lifecycle(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_detail", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    action = request.POST.get("action")
    try:
        if action == "take_under_review":
            if not can_plan_dispatch(request):
                raise PermissionDenied("Only dispatchers can take a dispatch under review.")
            ctx.take_under_review()
            messages.success(request, "Dispatch marked under review.")
        elif action == "request_fixes":
            if not can_plan_dispatch(request):
                raise PermissionDenied("Only dispatchers can request fixes.")
            reason = request.POST.get("reason", "").strip()
            ctx.request_fixes(reason=reason)
            messages.warning(request, "Fixes requested on dispatch.")
        elif action == "resubmit":
            ctx.resubmit()
            messages.success(request, "Dispatch resubmitted as Requested.")
        elif action == "mark_completed":
            if not can_complete_dispatch(request):
                raise PermissionDenied("You do not have permission to mark a dispatch completed.")
            ctx.mark_completed()
            messages.success(request, "Dispatch completed.")
        else:
            messages.error(request, "Unknown lifecycle action.")
    except (ValueError, PermissionDenied) as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_detail", pk=pk)


@login_required
def dispatch_update_intent(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    fields = {}
    posted_fields = ["title", "description", "priority", "activity_location", "names_free_text"]
    if IntentLockPolicy.is_fully_editable(ctx.dispatch):
        posted_fields.extend([
            "asset_class_id", "asset_subclass_text", "desired_start", "desired_end",
            "headcount", "requested_assets", "dispatch_scope", "estimated_meter_usage", "requested_for_id"
        ])

    for field in posted_fields:
        if field in request.POST:
            val = request.POST.get(field)
            if field in ("asset_class_id", "requested_for_id") and val:
                fields[field] = int(val)
            elif field in ("headcount",) and val:
                fields[field] = int(val)
            elif field in ("estimated_meter_usage",) and val:
                fields[field] = float(val)
            else:
                fields[field] = val

    try:
        ctx.update_intent(**fields)
        messages.success(request, "Dispatch details updated.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_edit", pk=pk)


@login_required
def dispatch_requirement_action(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    action = request.POST.get("action")
    kind = request.POST.get("kind")

    try:
        if action == "add":
            target_id_raw = request.POST.get("target_id") or request.POST.get("picked_id")
            if not target_id_raw or not target_id_raw.isdigit():
                raise ValueError("Pick a value before adding a requirement.")
            target_id = int(target_id_raw)
            is_required = request.POST.get("is_required") == "on" or request.POST.get("is_required") == "true"
            notes = request.POST.get("notes", "").strip()
            qty_raw = request.POST.get("quantity")
            quantity = int(qty_raw) if qty_raw and qty_raw.isdigit() else None
            lvl_raw = request.POST.get("minimum_level")
            minimum_level = int(lvl_raw) if lvl_raw and lvl_raw.isdigit() else None
            config_id_raw = request.POST.get("configuration_template_id")
            config_id = int(config_id_raw) if config_id_raw and config_id_raw.isdigit() else None

            ctx.requirements.add(
                kind=kind,
                target_id=target_id,
                is_required=is_required,
                notes=notes,
                quantity=quantity,
                minimum_level=minimum_level,
                configuration_template_id=config_id,
                actor=request.user,
            )
            messages.success(request, f"Added {kind} requirement.")
        elif action == "remove":
            req_id = int(request.POST.get("requirement_id"))
            ctx.requirements.remove(kind=kind, requirement_id=req_id, actor=request.user)
            messages.success(request, f"Removed {kind} requirement.")
    except IntegrityError:
        messages.error(request, "That requirement is already on this dispatch.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_edit", pk=pk)


@login_required
def dispatch_demand_action(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    action = request.POST.get("action")
    try:
        if action in ("raise", "add_material_requirement"):
            part_id_raw = request.POST.get("part_id")
            if not part_id_raw or not part_id_raw.isdigit():
                raise ValueError("Pick a part before adding a material requirement.")
            part_id = int(part_id_raw)
            qty_raw = request.POST.get("quantity_requested") or request.POST.get("quantity", "1")
            qty = Decimal(str(qty_raw))
            notes = request.POST.get("notes", "").strip()
            ctx.demands.raise_demand(part_id=part_id, quantity_requested=qty, notes=notes, actor=request.user)
            messages.success(request, "Material demand raised.")
        elif action in ("cancel", "remove_material_requirement"):
            demand_id_raw = request.POST.get("part_demand_id") or request.POST.get("demand_id")
            if not demand_id_raw or not demand_id_raw.isdigit():
                raise ValueError("Invalid part demand.")
            demand_id = int(demand_id_raw)
            reason = request.POST.get("reason", "").strip() or "Cancelled from dispatch edit."
            from app.parts.control_layer.part_demand_context import PartDemandContext
            PartDemandContext(demand_id).cancel(actor=request.user, notes=reason)
            messages.success(request, "Part demand cancelled.")
    except (ValueError, TransitionRefused) as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_edit", pk=pk)


@login_required
def dispatch_crew_action(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    action = request.POST.get("action")
    try:
        if action == "add":
            user_id = int(request.POST.get("user_id"))
            role = request.POST.get("role", PersonnelRole.PASSENGER)
            notes = request.POST.get("notes", "").strip()
            ctx.crew.add(user_id=user_id, role=role, notes=notes, actor=request.user)
            messages.success(request, "Crew member added.")
        elif action == "remove":
            crew_id = int(request.POST.get("crew_id"))
            ctx.crew.remove(crew_id=crew_id, actor=request.user)
            messages.success(request, "Crew member removed.")
    except ValueError as exc:
        messages.error(request, str(exc))

    if request.headers.get("HX-Request"):
        username_q = request.POST.get("user_name", "").strip() or request.GET.get("user_name", "").strip()
        skill_q = request.POST.get("skill_name", "").strip() or request.GET.get("skill_name", "").strip()
        include_overlapping = (request.POST.get("include_overlapping") or request.GET.get("include_overlapping")) in ("on", "true", "1")

        # Reload fresh context so struct contains updated crew roster
        fresh_ctx = DispatchContext(pk, request.user)
        available_users, overlapping_user_ids = _get_available_personnel_context(
            fresh_ctx.dispatch,
            username_q=username_q,
            skill_q=skill_q,
            include_overlapping=include_overlapping,
        )
        context = {
            "dispatch": fresh_ctx.dispatch,
            "struct": fresh_ctx.struct,
            "available_users": available_users,
            "overlapping_user_ids": overlapping_user_ids,
            "username_q": username_q,
            "skill_q": skill_q,
            "include_overlapping": include_overlapping,
            "personnel_roles": PersonnelRole.choices,
        }
        return render(request, "dispatching/dispatches/_personnel_card.html", context)

    return redirect("dispatching_dispatch_edit", pk=pk)


@login_required
def dispatch_expense_action(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    action = request.POST.get("action")
    try:
        if action == "add":
            expense_type = request.POST.get("expense_type", ExpenseType.CONTRACT)
            reason = request.POST.get("reason", "").strip()
            amount = Decimal(request.POST.get("amount", "0"))
            vendor_id = int(request.POST.get("counterparty_vendor_id")) if request.POST.get("counterparty_vendor_id") else None
            vendor_name = request.POST.get("counterparty_name", "").strip()
            payee_id = int(request.POST.get("payee_id")) if request.POST.get("payee_id") else None
            ext_ref = request.POST.get("external_reference", "").strip()
            notes = request.POST.get("notes", "").strip()

            ctx.expenses.add(
                expense_type=expense_type,
                reason=reason,
                amount=amount,
                counterparty_vendor_id=vendor_id,
                counterparty_name=vendor_name,
                payee_id=payee_id,
                external_reference=ext_ref,
                notes=notes,
                actor=request.user,
            )
            messages.success(request, "Expense added.")
        elif action == "commit":
            exp_id = int(request.POST.get("expense_id"))
            ctx.expenses.commit(expense_id=exp_id, actor=request.user)
            messages.success(request, "Expense committed.")
        elif action == "complete":
            exp_id = int(request.POST.get("expense_id"))
            ctx.expenses.complete(expense_id=exp_id, actor=request.user)
            messages.success(request, "Expense completed.")
        elif action == "cancel":
            exp_id = int(request.POST.get("expense_id"))
            reason = request.POST.get("reason", "").strip()
            ctx.expenses.cancel(expense_id=exp_id, reason=reason, actor=request.user)
            messages.success(request, "Expense cancelled.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_edit", pk=pk)


@login_required
def dispatch_reject(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_detail", pk=pk)

    if not can_reject_dispatch(request):
        raise PermissionDenied("You do not have permission to reject dispatches.")

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    reason = request.POST.get("reason", "").strip()
    category = request.POST.get("category", "").strip()
    suggestion = request.POST.get("alternative_suggestion", "").strip()
    can_resubmit = request.POST.get("can_resubmit") == "on" or request.POST.get("can_resubmit") == "true"

    try:
        ctx.rejection.reject(
            reason=reason,
            category=category,
            alternative_suggestion=suggestion,
            can_resubmit=can_resubmit,
            actor=request.user,
        )
        messages.warning(request, f"Dispatch #{pk} has been rejected.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_detail", pk=pk)


@login_required
def dispatch_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_detail", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    reason = request.POST.get("reason", "").strip()
    try:
        result = ctx.cancellation.cancel(reason=reason, actor=request.user)
        messages.info(request, f"Dispatch #{pk} has been cancelled.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_detail", pk=pk)


@login_required
def dispatch_supersede(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_detail", pk=pk)

    if not can_raise_dispatch(request):
        raise PermissionDenied("You do not have permission to raise a superseding dispatch.")

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    try:
        new_dispatch = ctx.supersession.supersede(actor=request.user)
        messages.success(request, f"Superseding dispatch #{new_dispatch.pk} created.")
        return redirect("dispatching_dispatch_edit", pk=new_dispatch.pk)
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_detail", pk=pk)


@login_required
def dispatch_attach_reservation(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("dispatching_dispatch_edit", pk=pk)

    try:
        ctx = DispatchContext(pk, request.user)
    except DispatchingDetail.DoesNotExist:
        raise Http404("Dispatch not found.")

    res_id = int(request.POST.get("reservation_id"))
    try:
        ReservationPromotionManager.promote(reservation_id=res_id, dispatch_id=pk, actor=request.user)
        messages.success(request, f"Attached reservation #{res_id} to dispatch.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("dispatching_dispatch_edit", pk=pk)
