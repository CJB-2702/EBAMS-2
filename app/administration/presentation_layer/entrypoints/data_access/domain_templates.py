"""Domain templates: list / detail / edit / create / delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.data_ownership.domain_assignment_policy_guard import (
    DomainAccessDenied,
    assert_actor_may_edit_domain_templates,
)
from app.administration.control_layer.data_ownership.domain_template_context import (
    DomainTemplateContext,
)
from app.administration.control_layer.permissions.permission_grant_guard import (
    is_admin_actor,
)
from app.administration.models import (
    Domain,
    DomainTemplate,
    DomainTemplateItem,
    UserDomainTemplate,
)


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify domain templates.",
        )
    return None


def _parse_id_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        try:
            out.append(int(raw))
        except ValueError:
            continue
    return out


def _unique_slug(name: str) -> str:
    base = slugify(name) or "template"
    slug = base
    i = 2
    while DomainTemplate.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


@require_http_methods(["GET"])
def domain_template_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = (
        DomainTemplate.objects.order_by("name")
        .annotate(
            active_item_count=Count("items", filter=Q(items__is_active=True), distinct=True),
            assignee_count=Count(
                "user_assignment_links",
                filter=Q(user_assignment_links__is_active=True),
                distinct=True,
            ),
        )
    )
    if q:
        qs = qs.filter(name__icontains=q)
    return render(
        request,
        "data_access/domain_templates/index.html",
        {
            "templates": qs,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def domain_template_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        if not name:
            messages.error(request, "Template name is required.")
            return render(
                request,
                "data_access/domain_templates/new.html",
                {"name": name, "description": description},
            )
        template = DomainTemplate.objects.create(
            name=name,
            slug=_unique_slug(name),
            description=description,
            is_active=True,
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Domain template '{template.name}' created.")
        return redirect(
            reverse("domain_template_detail", kwargs={"template_slug": template.slug}),
        )

    return render(request, "data_access/domain_templates/new.html", {})


@require_http_methods(["GET"])
def domain_template_detail(request: HttpRequest, template_slug: str) -> HttpResponse:
    template = get_object_or_404(DomainTemplate, slug=template_slug)
    items = (
        DomainTemplateItem.objects.filter(template=template, is_active=True)
        .select_related("domain")
        .order_by("domain__name")
    )
    domains = [item.domain for item in items]
    assignees = (
        UserDomainTemplate.objects.filter(template=template, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "data_access/domain_templates/detail.html",
        {
            "template": template,
            "domains": domains,
            "assignees": assignees,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def domain_template_edit(request: HttpRequest, template_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    template = get_object_or_404(DomainTemplate, slug=template_slug)

    if request.method == "POST":
        action = request.POST.get("action", "")
        actor = request.user
        ctx = DomainTemplateContext(template.pk)
        try:
            assert_actor_may_edit_domain_templates(actor)
            if action == "update_metadata":
                name = request.POST.get("name", "").strip() or None
                description = request.POST.get("description", "")
                ctx.update_metadata(actor=actor, name=name, description=description)
                messages.success(request, "Template details updated.")
            elif action == "set_active":
                is_active = request.POST.get("is_active") == "1"
                ctx.set_active(actor=actor, is_active=is_active)
                messages.success(
                    request,
                    "Template activated." if is_active else "Template deactivated.",
                )
            elif action == "add_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                if not ids:
                    messages.error(request, "Select at least one domain.")
                else:
                    with transaction.atomic():
                        for did in ids:
                            ctx.add_domain(actor=actor, domain_id=did)
                    messages.success(request, "Domains added to template.")
            elif action == "remove_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                if not ids:
                    messages.error(request, "Select at least one domain.")
                else:
                    with transaction.atomic():
                        for did in ids:
                            ctx.remove_domain(actor=actor, domain_id=did)
                    messages.success(request, "Domains removed from template.")
            else:
                messages.error(request, "Unknown action.")
        except DomainAccessDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(
            reverse("domain_template_edit", kwargs={"template_slug": template.slug}),
        )

    items_assigned = (
        DomainTemplateItem.objects.filter(template=template, is_active=True)
        .select_related("domain")
        .order_by("domain__name")
    )
    domains_assigned = [item.domain for item in items_assigned]
    assigned_domain_ids = {d.pk for d in domains_assigned}
    domains_available = list(
        Domain.objects.exclude(pk__in=assigned_domain_ids).order_by("name"),
    )

    return render(
        request,
        "data_access/domain_templates/edit.html",
        {
            "template": template,
            "domains_assigned": domains_assigned,
            "domains_available": domains_available,
        },
    )


@require_http_methods(["POST"])
def domain_template_move_domains(request: HttpRequest, template_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    template = get_object_or_404(DomainTemplate, slug=template_slug)
    ids = _parse_id_list(request.POST, "domain_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one domain.", status=400)

    try:
        assert_actor_may_edit_domain_templates(request.user)
        ctx = DomainTemplateContext(template.pk)
        with transaction.atomic():
            for did in ids:
                if direction == "add":
                    ctx.add_domain(actor=request.user, domain_id=did)
                else:
                    ctx.remove_domain(actor=request.user, domain_id=did)
    except (DomainAccessDenied, ObjectDoesNotExist, ValueError) as exc:
        return HttpResponse(str(exc), status=400)

    items_assigned = (
        DomainTemplateItem.objects.filter(template=template, is_active=True)
        .select_related("domain")
        .order_by("domain__name")
    )
    domains_assigned = [item.domain for item in items_assigned]
    assigned_domain_ids = {d.pk for d in domains_assigned}
    domains_available = list(Domain.objects.exclude(pk__in=assigned_domain_ids).order_by("name"))

    msg = "Domains added to template." if direction == "add" else "Domains removed from template."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "data_access/domain_templates/_domains_dlb_only.html", {
        "template": template,
        "domains_available": domains_available,
        "domains_assigned": domains_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def domain_template_delete(request: HttpRequest, template_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    template = get_object_or_404(DomainTemplate, slug=template_slug)
    name = template.name
    try:
        template.delete()
        messages.success(request, f"Domain template '{name}' deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete template: {exc}")
        return redirect(
            reverse("domain_template_detail", kwargs={"template_slug": template.slug}),
        )
    return redirect(reverse("domain_template_index"))
