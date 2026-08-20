"""Dispatch templates — lineage list/detail plus the session-backed working
draft editor (dispatching_starter_kit/1_dispatch_templates.md §3,
build_phase_3_ui.md §2.2). Mirrors app.maintenance's template_builder
pattern: every draft mutation posts to one `_draft_update` endpoint and
redirects back to the editor GET, so the F5 rule holds and nothing reaches
the database until commit.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.models import Domain
from app.dispatching.control_layer.adapters.template_draft_session_adapter import (
    SESSION_KEY,
    TemplateDraftSessionAdapter,
)
from app.dispatching.control_layer.domain_structs.template_lineage_struct import (
    TemplateLineageStruct,
)
from app.dispatching.control_layer.template_context import TemplateContext
from app.dispatching.models.templates.dispatch_template import DispatchTemplate
from app.dispatching.presentation_layer.search.template_search import (
    search_templates_for_management,
)
from app.dispatching.presentation_layer.tools.dispatching_access import (
    accessible_domain_ids,
    can_author_templates,
    can_commit_templates,
    can_view_templates,
    is_in_domain,
)


def _resolve_requirement_rows(draft: dict) -> dict:
    """The session draft stores only ids per row (TemplateDraftSessionAdapter
    keeps no denormalized display data) — resolve display objects here, in
    the view, rather than joining in the template."""
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
        rows = draft["requirements"].get(kind, [])
        ids = [r[id_field] for r in rows]
        objects_by_id = {obj.pk: obj for obj in queryset.filter(pk__in=ids)}
        out[kind] = [
            {**row, "object": objects_by_id.get(row[id_field])} for row in rows
        ]

    # Configuration template is an attribute of a model row, not its own
    # requirement kind — resolve it onto the already-built "model" rows.
    config_ids = [r["configuration_template_id"] for r in out["model"] if r.get("configuration_template_id")]
    configs_by_id = {c.pk: c for c in ConfigurationTemplate.objects.filter(pk__in=config_ids)}
    out["model"] = [
        {**row, "configuration_template": configs_by_id.get(row.get("configuration_template_id"))}
        for row in out["model"]
    ]
    return out


def _resolve_material_rows(draft: dict) -> list[dict]:
    from app.parts.models import Part

    rows = draft.get("material_requirements", [])
    parts_by_id = {p.pk: p for p in Part.objects.filter(pk__in=[r["part_id"] for r in rows])}
    return [{**row, "part": parts_by_id.get(row["part_id"])} for row in rows]


def _draft_reference_lists(draft: dict) -> dict:
    from app.assets.models import AssetClass
    from app.events.models.details.dispatching import DispatchScope

    return {
        "asset_classes": AssetClass.objects.filter(is_active=True).order_by("name"),
        "dispatch_scope_choices": DispatchScope.choices,
    }


# ─────────────────────────────────────────────────────────────────────────
# Lineage — list, detail, retire/reinstate
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["GET"])
def template_index(request: HttpRequest) -> HttpResponse:
    if not can_view_templates(request):
        raise PermissionDenied("Viewing templates requires the template_author or dispatching_read permission.")

    domain_ids = accessible_domain_ids(request)
    show_all = request.GET.get("show") == "all"
    templates = search_templates_for_management(domain_ids=domain_ids, include_retired=show_all)
    if not show_all:
        templates = templates.filter(is_retired=False)

    return render(request, "dispatching/templates/index.html", {
        "templates": templates,
        "show_all": show_all,
        "domains": Domain.objects.filter(pk__in=domain_ids).order_by("name"),
        "can_author": can_author_templates(request),
        "has_draft": SESSION_KEY in request.session,
    })


@require_http_methods(["GET"])
def template_detail(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_view_templates(request):
        raise PermissionDenied("Viewing a template requires the template_author or dispatching_read permission.")

    struct = TemplateLineageStruct.load(template_id=pk)
    if not is_in_domain(request, struct.template.domain_id):
        raise Http404

    head = struct.head_revision
    manifest = None
    if head is not None:
        manifest = {
            "capabilities": list(head.requested_capabilities.select_related("capability_definition")),
            "skills": list(head.requested_skills.select_related("skill")),
            "models": list(
                head.requested_models
                .select_related("model", "model__asset_class", "configuration_template")
                .prefetch_related("model__manufacturers")
            ),
            "modifications": list(head.requested_modifications.select_related("defined_modification")),
            "materials": list(head.material_requirements.select_related("part")),
        }
    usage_count = head.dispatches_created.count() if head is not None else 0

    return render(request, "dispatching/templates/detail.html", {
        "template": struct.template,
        "head": head,
        "manifest": manifest,
        "usage_count": usage_count,
        "revisions": struct.revisions,
        "can_author": can_author_templates(request),
        "can_commit": can_commit_templates(request),
    })


@require_http_methods(["POST"])
def template_retire(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_commit_templates(request):
        raise PermissionDenied("Retiring a template requires the template_commit permission.")

    struct = TemplateLineageStruct.load(template_id=pk)
    if not is_in_domain(request, struct.template.domain_id):
        raise Http404

    reason = request.POST.get("reason", "").strip()
    ctx = TemplateContext(pk, request.user)
    try:
        ctx.retire(reason=reason)
        messages.success(request, "Template retired.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(reverse("dispatching_template_detail", kwargs={"pk": pk}))


@require_http_methods(["POST"])
def template_reinstate(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_commit_templates(request):
        raise PermissionDenied("Reinstating a template requires the template_commit permission.")

    struct = TemplateLineageStruct.load(template_id=pk)
    if not is_in_domain(request, struct.template.domain_id):
        raise Http404

    TemplateContext(pk, request.user).reinstate()
    messages.success(request, "Template reinstated.")
    return redirect(reverse("dispatching_template_detail", kwargs={"pk": pk}))


# ─────────────────────────────────────────────────────────────────────────
# Working draft — session-backed, zero DB writes until commit (R3)
# ─────────────────────────────────────────────────────────────────────────

@require_http_methods(["POST"])
def template_draft_start_new(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied("Starting a template draft requires the template_author permission.")

    domain_id_raw = request.POST.get("domain_id", "").strip()
    domain_id = int(domain_id_raw) if domain_id_raw.isdigit() else None
    if domain_id not in accessible_domain_ids(request):
        messages.error(request, "You may only start a template in a domain you are assigned to.")
        return redirect(reverse("dispatching_template_index"))

    TemplateDraftSessionAdapter.start_new(request, domain_id=domain_id)
    messages.success(request, "Started a new template draft. Nothing is saved until you commit.")
    return redirect(reverse("dispatching_template_draft_editor"))


@require_http_methods(["POST"])
def template_draft_start_edit(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied("Editing a template draft requires the template_author permission.")

    template = get_object_or_404(DispatchTemplate, pk=pk)
    if not is_in_domain(request, template.domain_id):
        raise Http404

    try:
        TemplateDraftSessionAdapter.start_edit(request, template_id=pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("dispatching_template_detail", kwargs={"pk": pk}))

    messages.success(request, "Draft loaded from the head revision. Nothing is saved until you commit.")
    return redirect(reverse("dispatching_template_draft_editor"))


@require_http_methods(["POST"])
def template_draft_start_copy(request: HttpRequest, pk: int) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied("Copying a template requires the template_author permission.")

    template = get_object_or_404(DispatchTemplate, pk=pk)
    if not is_in_domain(request, template.domain_id):
        raise Http404

    try:
        TemplateDraftSessionAdapter.start_copy(request, template_id=pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("dispatching_template_detail", kwargs={"pk": pk}))

    messages.success(request, "Draft seeded from this template — committing will create a new, independent template.")
    return redirect(reverse("dispatching_template_draft_editor"))


@require_http_methods(["GET"])
def template_draft_editor(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied("Editing a template draft requires the template_author permission.")
    if SESSION_KEY not in request.session:
        messages.error(request, "No draft in progress — start a new template or edit an existing one.")
        return redirect(reverse("dispatching_template_index"))

    adapter = TemplateDraftSessionAdapter(request)
    draft = adapter.draft

    editing_template = None
    if draft.get("template_id"):
        editing_template = DispatchTemplate.objects.select_related(
            "domain", "head_revision__created_by"
        ).filter(pk=draft["template_id"]).first()

    copied_from_revision = None
    if draft.get("copied_from_revision_id"):
        from app.dispatching.models.templates.dispatch_template_revision import (
            DispatchTemplateRevision,
        )

        copied_from_revision = DispatchTemplateRevision.objects.select_related(
            "created_by", "template__domain"
        ).filter(pk=draft["copied_from_revision_id"]).first()

    context = {
        "draft": draft,
        "can_commit": can_commit_templates(request),
        "requirement_rows": _resolve_requirement_rows(draft),
        "material_rows": _resolve_material_rows(draft),
        "editing_template": editing_template,
        "copied_from_revision": copied_from_revision,
        **_draft_reference_lists(draft),
    }
    return render(request, "dispatching/templates/draft_editor.html", context)


@require_http_methods(["POST"])
def template_draft_update(request: HttpRequest) -> HttpResponse:
    if not can_author_templates(request):
        raise PermissionDenied("Editing a template draft requires the template_author permission.")
    if SESSION_KEY not in request.session:
        messages.error(request, "No draft in progress.")
        return redirect(reverse("dispatching_template_index"))

    adapter = TemplateDraftSessionAdapter(request)
    action = request.POST.get("action", "")

    try:
        if action == "set_metadata":
            asset_class_id_raw = request.POST.get("asset_class_id", "").strip()
            meter_raw = request.POST.get("estimated_meter_usage", "").strip()
            headcount_raw = request.POST.get("headcount", "").strip()
            adapter.set_metadata(
                title=request.POST.get("title", "").strip(),
                asset_class_id=int(asset_class_id_raw) if asset_class_id_raw.isdigit() else None,
                asset_subclass_text=request.POST.get("asset_subclass_text", "").strip(),
                dispatch_scope=request.POST.get("dispatch_scope", "").strip(),
                activity_location=request.POST.get("activity_location", "").strip(),
                estimated_meter_usage=float(meter_raw) if meter_raw else None,
                headcount=int(headcount_raw) if headcount_raw.isdigit() else None,
                notes=request.POST.get("notes", "").strip(),
            )
        elif action == "set_change_note":
            adapter.set_metadata(change_note=request.POST.get("change_note", ""))
        elif action == "add_requirement":
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
            adapter.add_requirement(kind=kind, **fields)
        elif action == "remove_requirement":
            adapter.remove_requirement(kind=request.POST.get("kind", ""), temp_id=request.POST.get("temp_id", ""))
        elif action == "add_material_requirement":
            part_id_raw = request.POST.get("part_id", "").strip()
            qty_raw = request.POST.get("quantity", "").strip()
            if not part_id_raw.isdigit() or not qty_raw:
                raise ValueError("Pick a part and a quantity before adding a material requirement.")
            adapter.add_material_requirement(
                part_id=int(part_id_raw), quantity=float(qty_raw), notes=request.POST.get("notes", "").strip(),
            )
        elif action == "remove_material_requirement":
            adapter.remove_material_requirement(temp_id=request.POST.get("temp_id", ""))
        elif action == "clear":
            adapter.clear()
            messages.success(request, "Draft discarded. Nothing was saved.")
            return redirect(reverse("dispatching_template_index"))
        else:
            messages.error(request, "Unknown draft action.")
    except (ValueError, KeyError) as exc:
        messages.error(request, str(exc))

    return redirect(reverse("dispatching_template_draft_editor"))


@require_http_methods(["POST"])
def template_draft_commit(request: HttpRequest) -> HttpResponse:
    if not can_commit_templates(request):
        raise PermissionDenied("Committing a revision requires the template_commit permission.")
    if SESSION_KEY not in request.session:
        messages.error(request, "No draft in progress.")
        return redirect(reverse("dispatching_template_index"))

    adapter = TemplateDraftSessionAdapter(request)
    adapter.set_metadata(change_note=request.POST.get("change_note", ""))

    domain_id = adapter.draft.get("domain_id")
    if not is_in_domain(request, domain_id):
        raise Http404

    try:
        revision = adapter.commit(actor=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect(reverse("dispatching_template_draft_editor"))

    messages.success(request, f"'{revision.title}' — revision {revision.revision_number} committed.")
    return redirect(reverse("dispatching_template_detail", kwargs={"pk": revision.template_id}))
