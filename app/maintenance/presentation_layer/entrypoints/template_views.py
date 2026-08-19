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
from app.events.control_layer.managers.activity_thread_manager import ActivityThreadManager
from app.maintenance.control_layer.adapters.template_builder_session_adapter import (
    TemplateBuilderSessionAdapter,
)
from app.maintenance.control_layer.template_maintenance_context import (
    TemplateMaintenanceContext,
)
from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.presentation_layer.search.proto_action_search import (
    ProtoActionSearch,
)
from app.maintenance.presentation_layer.search.template_model_search import (
    models_for_class,
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

    # "Add step" card (Card 3): three sources, default is the library. Each
    # keeps its own filter state in the querystring so hx-push-url makes the
    # tab + filters shareable/refreshable, matching the PO create wizard's
    # item-selection card.
    step_source = request.GET.get("step_source", "library")
    if step_source not in ("library", "maintenance", "new"):
        step_source = "library"
    pool_q = request.GET.get("pool_q", "").strip()
    pool_model_id_raw = request.GET.get("pool_model_id", "").strip()
    pool_model_id = int(pool_model_id_raw) if pool_model_id_raw.isdigit() else None
    source_template_id_raw = request.GET.get("source_template_id", "").strip()
    source_template_id = (
        int(source_template_id_raw) if source_template_id_raw.isdigit() else None
    )

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
        "step_source": step_source,
        "pool_q": pool_q,
        "pool_model_id": pool_model_id,
        "source_template_id": source_template_id,
    }

    if step_source == "library":
        context["library_pool"] = ProtoActionSearch.library_pool(
            domain_ids=user_domain_ids, q=pool_q, used_on_model_id=pool_model_id
        )
    elif step_source == "maintenance" and source_template_id:
        context["source_template_actions"] = TemplateActionItem.objects.filter(
            template_action_set_id=source_template_id,
            template_action_set__domain_id__in=user_domain_ids,
            deleted_at__isnull=True,
        ).order_by("sequence_order")

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
        elif action == "add_action_from_template_item":
            adapter.add_action_from_template_item(
                template_action_item_id=int(request.POST.get("template_action_item_id", 0))
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

    # Preserve the "Add step" card's tab + filter state across the mutation
    # redirect — every row's form carries these along as hidden fields so a
    # single Add doesn't bounce the Planner back to the library default.
    from urllib.parse import urlencode

    preserved = {
        key: request.POST[key]
        for key in ("step_source", "pool_q", "pool_model_id", "source_template_id")
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
