"""Domains: list / detail / edit / create / delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.data_ownership.data_ownership_context import (
    DataOwnershipContext,
)
from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    is_admin_actor,
    is_grant_actor,
)
from app.administration.models import (
    Domain,
    Organization,
    OrganizationDomain,
    UserDomain,
)
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify domains.",
        )
    return None


def _require_grant(request: HttpRequest) -> HttpResponse | None:
    if not is_grant_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_manager, generic_admin, or superusers may change domain assignments.",
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
    base = slugify(name) or "domain"
    slug = base
    i = 2
    while Domain.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


@require_http_methods(["GET"])
def domain_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Domain.objects.order_by("name").prefetch_related("organizations")
    if q:
        qs = qs.filter(name__icontains=q)
    return render(
        request,
        "data_access/domains/index.html",
        {
            "domains": qs,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def domain_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Domain name is required.")
            return render(request, "data_access/domains/new.html", {"name": name})
        domain = Domain.objects.create(
            name=name,
            slug=_unique_slug(name),
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Domain '{domain.name}' created.")
        return redirect(reverse("domain_detail", kwargs={"domain_id": domain.pk}))

    return render(request, "data_access/domains/new.html", {})


@require_http_methods(["GET"])
def domain_detail(request: HttpRequest, domain_id: int) -> HttpResponse:
    domain = get_object_or_404(
        Domain.objects.prefetch_related("organizations"),
        pk=domain_id,
    )
    organizations = domain.organizations.order_by("name")
    user_assignments = (
        UserDomain.objects.filter(domain=domain, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "data_access/domains/detail.html",
        {
            "domain": domain,
            "organizations": organizations,
            "user_assignments": user_assignments,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def domain_edit(request: HttpRequest, domain_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    domain = get_object_or_404(
        Domain.objects.prefetch_related("organizations"),
        pk=domain_id,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        actor = request.user
        try:
            if action == "update_metadata":
                if not is_admin_actor(actor):
                    return HttpResponseForbidden("Admin only.")
                name = request.POST.get("name", "").strip()
                if name:
                    domain.name = name
                    domain.updated_by = actor
                    domain.save(update_fields=["name", "updated_at", "updated_by"])
                    messages.success(request, "Domain updated.")
            elif action == "add_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                if not ids:
                    messages.error(request, "Select at least one organization.")
                else:
                    with transaction.atomic():
                        for oid in ids:
                            OrganizationDomain.objects.get_or_create(
                                domain=domain,
                                organization_id=oid,
                                defaults={"created_by": actor, "updated_by": actor},
                            )
                    messages.success(request, "Organizations linked.")
            elif action == "remove_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                if not ids:
                    messages.error(request, "Select at least one organization.")
                else:
                    OrganizationDomain.objects.filter(
                        domain=domain,
                        organization_id__in=ids,
                    ).delete()
                    messages.success(request, "Organizations unlinked.")
            elif action == "add_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            DataOwnershipContext(uid).enable_or_assign_domain(
                                actor=actor,
                                domain_id=domain.pk,
                            )
                    messages.success(request, "Users assigned to domain.")
            elif action == "remove_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            row = UserDomain.objects.get(user_id=uid, domain_id=domain.pk)
                            DataOwnershipContext(uid).disable_domain_assignment(
                                actor=actor,
                                user_domain_id=row.pk,
                            )
                    messages.success(request, "Users removed from domain.")
            else:
                messages.error(request, "Unknown action.")
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("domain_edit", kwargs={"domain_id": domain.pk}))

    organizations_assigned = list(domain.organizations.order_by("name"))
    assigned_org_ids = {o.pk for o in organizations_assigned}
    organizations_available = list(
        Organization.objects.exclude(pk__in=assigned_org_ids).order_by("name"),
    )

    user_assignments = list(
        UserDomain.objects.filter(domain=domain, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_assigned = [ua.user for ua in user_assignments]
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    return render(
        request,
        "data_access/domains/edit.html",
        {
            "domain": domain,
            "organizations_assigned": organizations_assigned,
            "organizations_available": organizations_available,
            "users_assigned": users_assigned,
            "users_available": users_available,
            "can_edit_metadata": is_admin_actor(request.user),
        },
    )


@require_http_methods(["POST"])
def domain_move_organizations(request: HttpRequest, domain_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    domain = get_object_or_404(Domain, pk=domain_id)
    ids = _parse_id_list(request.POST, "organization_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one organization.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for oid in ids:
                if direction == "add":
                    OrganizationDomain.objects.get_or_create(
                        domain=domain,
                        organization_id=oid,
                        defaults={"created_by": actor, "updated_by": actor},
                    )
                else:
                    OrganizationDomain.objects.filter(domain=domain, organization_id=oid).delete()
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    assigned_ids = list(
        OrganizationDomain.objects.filter(domain=domain).values_list("organization_id", flat=True)
    )
    organizations_assigned = list(Organization.objects.filter(pk__in=assigned_ids).order_by("name"))
    organizations_available = list(Organization.objects.exclude(pk__in=assigned_ids).order_by("name"))

    msg = "Organizations linked." if direction == "add" else "Organizations unlinked."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "data_access/domains/_organizations_dlb_only.html", {
        "domain": domain,
        "organizations_available": organizations_available,
        "organizations_assigned": organizations_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def domain_move_users(request: HttpRequest, domain_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    domain = get_object_or_404(Domain, pk=domain_id)
    ids = _parse_id_list(request.POST, "user_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one user.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for uid in ids:
                if direction == "add":
                    DataOwnershipContext(uid).enable_or_assign_domain(actor=actor, domain_id=domain.pk)
                else:
                    row = UserDomain.objects.get(user_id=uid, domain_id=domain.pk)
                    DataOwnershipContext(uid).disable_domain_assignment(actor=actor, user_domain_id=row.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    user_assignments = list(
        UserDomain.objects.filter(domain=domain, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    users_assigned = [ua.user for ua in user_assignments]
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    msg = "Users assigned to domain." if direction == "add" else "Users removed from domain."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "data_access/domains/_users_dlb_only.html", {
        "domain": domain,
        "users_available": users_available,
        "users_assigned": users_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def domain_delete(request: HttpRequest, domain_id: int) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    domain = get_object_or_404(Domain, pk=domain_id)
    name = domain.name
    try:
        domain.delete()
        messages.success(request, f"Domain '{name}' deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete domain: {exc}")
        return redirect(reverse("domain_detail", kwargs={"domain_id": domain.pk}))
    return redirect(reverse("domain_index"))
