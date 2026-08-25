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
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.maintenance.control_layer.adapters.template_builder_session_adapter import (
    TemplateBuilderSessionAdapter,
)
from app.maintenance.control_layer.template_maintenance_context import (
    TemplateMaintenanceContext,
)
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.presentation_layer.search.template_model_search import (
    models_for_class,
)
from app.maintenance.presentation_layer.tools.action_creator import (
    CREATOR_TABS,
    creator_tab_context,
    normalize_tab,
)
from app.maintenance.presentation_layer.tools.maintenance_access import (
    accessible_domain_ids,
    is_in_domain,
)


@require_http_methods(["GET"])
def template_index(request: HttpRequest) -> HttpResponse:
    """Procedure template library index (D5-scoped). Doubles as the template
    build hub (legacy /manager/build-maintenance-templates): preview mode
    (?preview=1) adds a list/preview split with the from-existing actions
    (View, Edit → revision, Copy, Create event) atop the preview pane."""
    from django.db.models import Count, Q

    from app.assets.models import AssetModel
    from app.assets.models.core.asset_class import AssetClass
    from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem

    domain_ids = accessible_domain_ids(request)
    filters = {
        "q": request.GET.get("q", "").strip(),
        "domain_id": request.GET.get("domain_id", "").strip(),
        "asset_class_id": request.GET.get("asset_class_id", "").strip(),
        "model_id": request.GET.get("model_id", "").strip(),
        "active": request.GET.get("active", "").strip(),
        "preview": request.GET.get("preview", "").strip(),
        "selected": request.GET.get("selected", "").strip(),
    }
    # Default to preview mode (unless explicitly disabled with preview=0)
    preview_mode = filters["preview"] != "0"
    qs = TemplateActionSet.objects.filter(
        domain_id__in=domain_ids, deleted_at__isnull=True
    ).select_related("domain", "asset_class").prefetch_related("asset_models").annotate(
        action_count=Count("template_action_items", distinct=True),
        subsequent_revision_count=Count(
            "subsequent_revisions",
            filter=Q(subsequent_revisions__deleted_at__isnull=True),
            distinct=True,
        ),
    )
    if filters["q"]:
        qs = qs.filter(task_name__icontains=filters["q"])
    if filters["domain_id"].isdigit():
        qs = qs.filter(domain_id=int(filters["domain_id"]))
    if filters["asset_class_id"].isdigit():
        qs = qs.filter(asset_class_id=int(filters["asset_class_id"]))
    if filters["model_id"].isdigit():
        qs = qs.filter(asset_models__id=int(filters["model_id"])).distinct()
    if filters["active"] == "active":
        qs = qs.filter(is_active=True)
    elif filters["active"] == "inactive":
        qs = qs.filter(is_active=False)
    templates = list(qs.order_by("task_name"))

    # The preview pane — never blank; auto-select first template if none chosen.
    selected, selected_steps = None, []
    if preview_mode:
        selected_id = None
        if filters["selected"].isdigit():
            selected_id = int(filters["selected"])
        elif templates:
            selected_id = templates[0].pk
            filters["selected"] = str(selected_id)

        if selected_id:
            selected = next((t for t in templates if t.pk == selected_id), None)
            if selected:
                tctx = TemplateMaintenanceContext(selected.pk)
                items = list(tctx.template_action_items)
                tools_by_action = tctx.get_tools_by_action()
                part_demands_by_action = tctx.get_part_demands_by_action()
                selected_steps = [
                    {
                        "item": item,
                        "tools": tools_by_action.get(item.pk, []),
                        "parts": part_demands_by_action.get(item.pk, []),
                    }
                    for item in items
                ]

    context = {
        "templates": templates,
        "filters": filters,
        "preview_mode": preview_mode,
        "selected": selected,
        "selected_steps": selected_steps,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "asset_classes": AssetClass.objects.all().order_by("name"),
        "models_for_filter": AssetModel.objects.all().order_by(
            "model_name", "version_rank", "version"
        ),
        "draft": TemplateBuilderSessionAdapter(request).draft,
        "proto_count": ProtoActionItem.objects.filter(
            domain_id__in=domain_ids, deleted_at__isnull=True
        ).count(),
    }
    results_template = (
        "maintenance/_template_index_preview_split.html"
        if preview_mode
        else "maintenance/_template_index_results.html"
    )
    if request.GET.get("format") == "htmx-search-results":
        return render(request, results_template, context)
    return render(request, "maintenance/template_index.html", context)


@require_http_methods(["GET"])
def template_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Read-only view of a committed procedure template."""
    template = get_object_or_404(
        TemplateActionSet.objects.select_related("domain", "asset_class").prefetch_related(
            "asset_models"
        ),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, template.domain_id):
        raise Http404
    tctx = TemplateMaintenanceContext(pk)
    items = list(tctx.template_action_items)
    assigned_models = list(tctx.asset_models)
    assigned_model_ids = {m.pk for m in assigned_models}
    models_available = [
        m for m in models_for_class(template.asset_class_id) if m.pk not in assigned_model_ids
    ]
    tools_by_action = tctx.get_tools_by_action()
    part_demands_by_action = tctx.get_part_demands_by_action()
    all_parts = tctx.all_parts_required
    all_tools = tctx.all_tools_required
    steps = [
        {
            "item": item,
            "tools": tools_by_action.get(item.pk, []),
            "parts": part_demands_by_action.get(item.pk, []),
        }
        for item in items
    ]
    context = {
        "template": template,
        "steps": steps,
        "total_estimated_duration_minutes": tctx.total_estimated_duration_minutes,
        "total_action_items": tctx.total_action_items,
        "all_parts_required": all_parts,
        "all_tools_required": all_tools,
        "models_assigned": assigned_models,
        "models_available": models_available,
        # Advisory nudge toward the proto-action library — only worth
        # showing when a step isn't already backed by one.
        "has_adhoc_steps": any(item.proto_action_item_id is None for item in items),
        "is_newest_revision": tctx.is_newest_revision,
        "revision_chain": tctx.revision_chain,
        "comments_card": ActivityThreadManager(template, thread_attr="activity_thread").card(request.user),
    }
    return render(request, "maintenance/template_detail.html", context)


@require_http_methods(["POST"])
def template_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    """Flip a committed template's active flag (legacy /active_status)."""
    template = get_object_or_404(
        TemplateActionSet.objects.only("pk", "domain_id", "is_active", "task_name"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, template.domain_id):
        raise Http404

    tctx = TemplateMaintenanceContext(pk)
    if template.is_active:
        tctx.deactivate(actor=request.user)
        messages.success(request, f"'{template.task_name}' deactivated.")
    else:
        tctx.activate(actor=request.user)
        messages.success(request, f"'{template.task_name}' activated.")
    return redirect(reverse("template_detail", kwargs={"pk": pk}))


@require_http_methods(["POST"])
def template_move_asset_models(request: HttpRequest, pk: int) -> HttpResponse:
    """Dual-listbox move endpoint for the template's model tags (HTMX-only,
    mirrors permission_group_move_permissions)."""
    template = get_object_or_404(
        TemplateActionSet.objects.select_related("asset_class"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if not is_in_domain(request, template.domain_id):
        raise Http404

    ids = [
        int(v) for v in request.POST.getlist("asset_model_ids") if str(v).strip().isdigit()
    ]
    direction = request.POST.get("direction", "add")
    if not ids:
        return HttpResponse("Select at least one model.", status=400)

    tctx = TemplateMaintenanceContext(pk)
    if direction == "add":
        # Scope adds to the template's own asset class — the picker only ever
        # offers these, but a POST could be forged, so re-filter server-side.
        ids = list(
            models_for_class(template.asset_class_id).filter(pk__in=ids).values_list(
                "pk", flat=True
            )
        )
        tctx.add_asset_models(ids, actor=request.user)
        msg = "Models added to template."
    else:
        tctx.remove_asset_models(ids, actor=request.user)
        msg = "Models removed from template."

    assigned_models = list(tctx.asset_models)
    assigned_model_ids = {m.pk for m in assigned_models}
    models_available = [
        m for m in models_for_class(template.asset_class_id) if m.pk not in assigned_model_ids
    ]

    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(
        request,
        "maintenance/components/_template_models_dlb_only.html",
        {
            "template": template,
            "models_available": models_available,
            "models_assigned": assigned_models,
        },
    ).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


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
        elif action == "start_copy":
            template_id = int(request.POST.get("template_action_set_id", 0))
            TemplateBuilderSessionAdapter.start_copy(
                request, template_action_set_id=template_id
            )
            messages.success(request, "Draft copied from existing template — this will publish as an independent template.")
        elif action == "start_blank":
            adapter = TemplateBuilderSessionAdapter(request)
            adapter.clear()
            TemplateBuilderSessionAdapter(request)  # reseed a blank draft
            messages.success(request, "Started a new blank draft.")
        return redirect(reverse("template_builder"))

    from app.assets.models import AssetModel
    from app.assets.models.core.asset_class import AssetClass

    adapter = TemplateBuilderSessionAdapter(request)
    user_domain_ids = list(request.user.get_all_domain_ids())
    all_models = AssetModel.objects.all().order_by(
        "asset_class_id", "model_name", "version_rank", "version"
    )
    draft_asset_class_id = adapter.draft.get("asset_class_id")
    draft_asset_model_ids = adapter.draft.get("asset_model_ids", [])
    models_for_builder_class = list(models_for_class(draft_asset_class_id))
    models_assigned = [m for m in models_for_builder_class if m.pk in draft_asset_model_ids]
    models_available = [m for m in models_for_builder_class if m.pk not in draft_asset_model_ids]
    existing_templates = TemplateActionSet.objects.filter(
        domain_id__in=user_domain_ids, deleted_at__isnull=True, is_active=True
    ).order_by("task_name")

    # The Add-step card is the shared Action Creator Portal — the same five
    # sources and the same tab strip the event edit portal renders. Its source
    # + filters live in the querystring so they stay shareable and F5-safe.
    tab = normalize_tab(request.GET.get("tab"))
    q = request.GET.get("q", "").strip()
    pool_model_id_raw = request.GET.get("pool_model_id", "").strip()
    pool_model_id = int(pool_model_id_raw) if pool_model_id_raw.isdigit() else None

    # Part/tool pickers on the step rows are search dropdowns against this same
    # URL, per the format= contract.
    fragment = request.GET.get("format", "")
    if fragment == "htmx-part-search":
        return _builder_part_search(request)
    if fragment == "htmx-tool-search":
        return _builder_tool_search(request)

    context = {
        "draft": adapter.draft,
        "domains": Domain.objects.filter(pk__in=user_domain_ids).order_by("name"),
        "show_domain_picker": len(user_domain_ids) > 1,
        "single_domain_id": user_domain_ids[0] if len(user_domain_ids) == 1 else None,
        "existing_templates": existing_templates,
        "asset_classes": AssetClass.objects.all().order_by("name"),
        "all_models": all_models,
        "models_available": models_available,
        "models_assigned": models_assigned,
        "draft_actions": _draft_actions_for_display(adapter.draft),
        # Action Creator Portal host contract — see _action_creator.html.
        "tabs": CREATOR_TABS,
        "tab": tab,
        "q": q,
        "pool_model_id": pool_model_id,
        "model_filter": all_models,
        "creator_url": reverse("template_builder"),
        "creator_post_url": reverse("template_builder_update"),
        # Which step row was left open — carried across mutation redirects so
        # adding a tool does not collapse the row you were working in.
        "open_step": request.GET.get("open_step", ""),
    }
    context.update(
        creator_tab_context(
            tab=tab,
            q=q,
            domain_ids=user_domain_ids,
            asset_class_id=draft_asset_class_id,
            asset_model_ids=draft_asset_model_ids,
            used_on_model_id=pool_model_id,
            current_actions=context["draft_actions"] if tab == "current" else None,
        )
    )

    if request.GET.get("format") == "htmx-creator":
        return render(request, "maintenance/work/_action_creator.html", context)

    return render(request, "maintenance/template_builder.html", context)


def _draft_actions_for_display(draft: dict) -> list:
    """The draft's steps as render-ready rows.

    The session dict stores ids; the page has to show names. Rather than let
    the template index dicts (which it cannot do for a variable key anyway),
    the labels are resolved here, and the rows carry the per-row flags the
    step list needs — first/last for the reorder buttons, and a stable
    child index for the remove forms.
    """
    actions = draft.get("actions", [])
    total = len(actions)
    rows = []
    for index, action in enumerate(actions):
        tools = [
            {
                "index": i,
                "label": tool.get("tool_name") or f"tool #{tool.get('tool_id')}",
                "quantity_required": tool.get("quantity_required", 1),
                "specifications": tool.get("specifications", ""),
            }
            for i, tool in enumerate(action.get("tools", []))
        ]
        demands = [
            {
                "index": i,
                "part_id": demand.get("part_id"),
                "part_label": demand.get("part_label", ""),
                "quantity_required": demand.get("quantity_required", 1),
                "is_optional": demand.get("is_optional", False),
            }
            for i, demand in enumerate(action.get("part_demands", []))
        ]
        rows.append(
            {
                # `pk` so the shared creator partial's "From Current Build"
                # source can address a draft row the same way it addresses a
                # saved Action on the event edit portal.
                "pk": action["temp_id"],
                "temp_id": action["temp_id"],
                "sequence_order": action.get("sequence_order", index + 1),
                "action_name": action.get("action_name", ""),
                "description": action.get("description", ""),
                "instructions": action.get("instructions", ""),
                "safety_notes": action.get("safety_notes", ""),
                "estimated_duration_minutes": action.get("estimated_duration_minutes"),
                "tools": tools,
                "part_demands": demands,
                "is_first": index == 0,
                "is_last": index == total - 1,
            }
        )
    return rows


def _builder_part_search(request: HttpRequest) -> HttpResponse:
    """Result rows for the step rows' <search-dropdown name="part_id">."""
    from app.parts.models.core.part import Part

    q = request.GET.get("q", "").strip()
    parts = Part.objects.all()
    if q:
        parts = parts.filter(Q(part_number__icontains=q) | Q(name__icontains=q))
    return render(
        request,
        "maintenance/part_demands/_part_search_results.html",
        {"parts": parts.order_by("part_number")[:25]},
    )


def _builder_tool_search(request: HttpRequest) -> HttpResponse:
    """Result rows for the step rows' <search-dropdown name="tool_id">."""
    from app.parts.models.core.tool import Tool

    q = request.GET.get("q", "").strip()
    tools = Tool.objects.filter(is_active=True)
    if q:
        tools = tools.filter(Q(name__icontains=q) | Q(tool_type__icontains=q))
    return render(
        request,
        "maintenance/templates/_tool_search_results.html",
        {"tools": tools.order_by("name")[:25]},
    )


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
            )
        elif action == "set_revision_note":
            adapter.set_metadata(revision_note=request.POST.get("revision_note", ""))
        elif action == "add_asset_models":
            ids = [
                int(v) for v in request.POST.getlist("asset_model_ids") if v.strip().isdigit()
            ]
            # Re-scope to the draft's own asset class server-side — the pool the
            # card renders only ever offers these, but a POST could be forged.
            draft_asset_class_id = adapter.draft.get("asset_class_id")
            ids = list(
                models_for_class(draft_asset_class_id).filter(pk__in=ids).values_list(
                    "pk", flat=True
                )
            )
            adapter.add_asset_models(ids)
        elif action == "remove_asset_models":
            ids = [
                int(v) for v in request.POST.getlist("asset_model_ids") if v.strip().isdigit()
            ]
            adapter.remove_asset_models(ids)
        # The five Action Creator Portal verbs. Field names are the portal's,
        # not this endpoint's — the partial is shared with the event edit
        # portal and must post identically to both hosts.
        elif action == "add_blank_action":
            duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
            adapter.add_action(
                action_name=request.POST.get("action_name", "").strip(),
                description=request.POST.get("description", ""),
                instructions=request.POST.get("instructions", ""),
                safety_notes=request.POST.get("safety_notes", ""),
                notes=request.POST.get("notes", ""),
                estimated_duration_minutes=int(duration_raw) if duration_raw.isdigit() else None,
            )
        elif action == "add_from_proto":
            adapter.add_action_from_proto(
                proto_action_item_id=int(request.POST.get("proto_id", 0))
            )
        elif action == "add_from_template_action":
            adapter.add_action_from_template_item(
                template_action_item_id=int(request.POST.get("template_action_id", 0))
            )
        elif action == "add_from_template_set":
            added = adapter.add_actions_from_template_set(
                template_action_set_id=int(request.POST.get("template_action_set_id", 0))
            )
            messages.success(
                request, f"Added {len(added)} step{'' if len(added) == 1 else 's'} to the draft."
            )
        elif action == "duplicate_action":
            adapter.duplicate_action(temp_id=request.POST.get("action_id", ""))
        elif action == "update_action":
            duration_raw = request.POST.get("estimated_duration_minutes", "").strip()
            adapter.update_action(
                temp_id=request.POST.get("temp_id", ""),
                action_name=request.POST.get("action_name", "").strip(),
                description=request.POST.get("description", ""),
                instructions=request.POST.get("instructions", ""),
                safety_notes=request.POST.get("safety_notes", ""),
                estimated_duration_minutes=int(duration_raw) if duration_raw.isdigit() else None,
            )
        elif action == "move_action":
            adapter.move_action(
                temp_id=request.POST.get("temp_id", ""),
                direction=request.POST.get("direction", ""),
            )
        elif action == "remove_action":
            adapter.remove_action(temp_id=request.POST.get("temp_id", ""))
        elif action == "add_tool":
            if not request.POST.get("tool_id", "").strip().isdigit() and not request.POST.get("tool_name", "").strip():
                raise ValueError("Pick a tool from the search box, or type an ad-hoc name.")
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
            part_id_raw = request.POST.get("part_id", "").strip()
            if not part_id_raw.isdigit():
                raise ValueError("Pick a part from the search box before adding it.")
            adapter.add_part_demand(
                temp_id=request.POST.get("temp_id", ""),
                part_id=int(part_id_raw),
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

    # Preserve the creator's source + filter state, and which step row was
    # open, across the mutation redirect — every form carries these along as
    # hidden fields so one Add doesn't bounce the Planner back to the default
    # source with every row collapsed.
    from urllib.parse import urlencode

    preserved = {
        key: request.POST[key]
        for key in ("tab", "q", "pool_model_id", "open_step")
        if request.POST.get(key)
    }
    url = reverse("template_builder")
    if preserved:
        url = f"{url}?{urlencode(preserved)}"
    return redirect(url)


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

    # Persist whatever the Publish card's revision-note field held so a
    # validation failure below redisplays it instead of losing it.
    adapter.set_metadata(revision_note=request.POST.get("revision_note", ""))

    if adapter.draft.get("prior_revision_id") and request.POST.get("acknowledge_retirement") != "on":
        messages.error(
            request,
            "You must acknowledge that publishing this revision will retire the prior one.",
        )
        return redirect(reverse("template_builder"))

    try:
        template = adapter.commit(domain_id=domain_id, actor=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("template_builder"))

    messages.success(request, f"Template '{template.task_name}' published.")
    return redirect(reverse("template_detail", kwargs={"pk": template.pk}))
