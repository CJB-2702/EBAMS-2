"""Organizations: list / detail / edit / create / delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.data_ownership.data_ownership_context import (
    DataOwnershipContext,
)
from app.administration.control_layer.data_ownership.division_structure import (
    link_organization_to_division,
    unlink_organization_from_division,
)
from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    is_admin_actor,
    is_grant_actor,
)
from app.administration.models import (
    Division,
    Domain,
    Organization,
    OrganizationDomain,
    UserOrganization,
)
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify organizations.",
        )
    return None


def _require_grant(request: HttpRequest) -> HttpResponse | None:
    if not is_grant_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_manager, generic_admin, or superusers may change organization assignments.",
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
    base = slugify(name) or "organization"
    slug = base
    i = 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


@require_http_methods(["GET"])
def organization_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = (
        Organization.objects.order_by("name")
        .prefetch_related("divisions")
        .annotate(domain_count=Count("domains", distinct=True))
    )
    if q:
        qs = qs.filter(name__icontains=q)
    return render(
        request,
        "organizational/organizations/index.html",
        {
            "organizations": qs,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def organization_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    divisions = Division.objects.order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        division_id_raw = request.POST.get("division_id", "").strip()
        if not name:
            messages.error(request, "Organization name is required.")
            return render(
                request,
                "organizational/organizations/new.html",
                {"name": name, "divisions": divisions},
            )
        org = Organization.objects.create(
            name=name,
            slug=_unique_slug(name),
            created_by=request.user,
            updated_by=request.user,
        )
        if division_id_raw.isdigit():
            try:
                link_organization_to_division(
                    actor=request.user,
                    organization_id=org.pk,
                    division_id=int(division_id_raw),
                )
            except (ObjectDoesNotExist, GrantPermissionDenied) as exc:
                messages.warning(request, f"Organization created but division link failed: {exc}")
        messages.success(request, f"Organization '{org.name}' created.")
        return redirect(reverse("organization_detail", kwargs={"organization_id": org.pk}))

    return render(
        request,
        "organizational/organizations/new.html",
        {"divisions": divisions},
    )


@require_http_methods(["GET"])
def organization_detail(request: HttpRequest, organization_id: int) -> HttpResponse:
    organization = get_object_or_404(
        Organization.objects.prefetch_related("divisions", "domains"),
        pk=organization_id,
    )
    domains = organization.domains.order_by("name")
    division = organization.division
    user_assignments = (
        UserOrganization.objects.filter(organization=organization, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "organizational/organizations/detail.html",
        {
            "organization": organization,
            "division": division,
            "domains": domains,
            "user_assignments": user_assignments,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def organization_edit(request: HttpRequest, organization_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    organization = get_object_or_404(
        Organization.objects.prefetch_related("divisions", "domains"),
        pk=organization_id,
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
                    organization.name = name
                    organization.updated_by = actor
                    organization.save(update_fields=["name", "updated_at", "updated_by"])
                    messages.success(request, "Organization updated.")
            elif action == "set_division":
                if not is_admin_actor(actor):
                    return HttpResponseForbidden("Admin only.")
                division_id_raw = request.POST.get("division_id", "").strip()
                current = organization.division
                if division_id_raw == "":
                    if current is not None:
                        unlink_organization_from_division(
                            actor=actor,
                            organization_id=organization.pk,
                            division_id=current.pk,
                        )
                        messages.success(request, "Division link removed.")
                else:
                    link_organization_to_division(
                        actor=actor,
                        organization_id=organization.pk,
                        division_id=int(division_id_raw),
                    )
                    messages.success(request, "Division updated.")
            elif action == "add_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                if not ids:
                    messages.error(request, "Select at least one domain.")
                else:
                    with transaction.atomic():
                        for did in ids:
                            OrganizationDomain.objects.get_or_create(
                                organization=organization,
                                domain_id=did,
                                defaults={"created_by": actor, "updated_by": actor},
                            )
                    messages.success(request, "Domains linked.")
            elif action == "remove_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                if not ids:
                    messages.error(request, "Select at least one domain.")
                else:
                    OrganizationDomain.objects.filter(
                        organization=organization,
                        domain_id__in=ids,
                    ).delete()
                    messages.success(request, "Domains removed.")
            elif action == "add_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            DataOwnershipContext(uid).enable_or_assign_organization(
                                actor=actor,
                                organization_id=organization.pk,
                            )
                    messages.success(request, "Users assigned.")
            elif action == "remove_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            row = UserOrganization.objects.get(
                                user_id=uid,
                                organization_id=organization.pk,
                            )
                            DataOwnershipContext(uid).disable_organization_assignment(
                                actor=actor,
                                user_organization_id=row.pk,
                            )
                    messages.success(request, "Users removed.")
            else:
                messages.error(request, "Unknown action.")
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("organization_edit", kwargs={"organization_id": organization.pk}))

    divisions = list(Division.objects.order_by("name"))
    current_division = organization.division

    domains_assigned = list(organization.domains.order_by("name"))
    assigned_domain_ids = {d.pk for d in domains_assigned}
    domains_available = list(
        Domain.objects.exclude(pk__in=assigned_domain_ids).order_by("name"),
    )

    user_assignments = list(
        UserOrganization.objects.filter(organization=organization, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_assigned = [ua.user for ua in user_assignments]
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    return render(
        request,
        "organizational/organizations/edit.html",
        {
            "organization": organization,
            "divisions": divisions,
            "current_division": current_division,
            "domains_assigned": domains_assigned,
            "domains_available": domains_available,
            "users_assigned": users_assigned,
            "users_available": users_available,
            "can_edit_metadata": is_admin_actor(request.user),
        },
    )


@require_http_methods(["POST"])
def organization_move_domains(request: HttpRequest, organization_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    organization = get_object_or_404(Organization, pk=organization_id)
    ids = _parse_id_list(request.POST, "domain_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one domain.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for did in ids:
                if direction == "add":
                    OrganizationDomain.objects.get_or_create(
                        organization=organization,
                        domain_id=did,
                        defaults={"created_by": actor, "updated_by": actor},
                    )
                else:
                    OrganizationDomain.objects.filter(
                        organization=organization, domain_id=did
                    ).delete()
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    assigned_ids = list(
        OrganizationDomain.objects.filter(organization=organization).values_list("domain_id", flat=True)
    )
    domains_assigned = list(Domain.objects.filter(pk__in=assigned_ids).order_by("name"))
    domains_available = list(Domain.objects.exclude(pk__in=assigned_ids).order_by("name"))

    msg = "Domains linked." if direction == "add" else "Domains removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "organizational/organizations/_domains_dlb_only.html", {
        "organization": organization,
        "domains_available": domains_available,
        "domains_assigned": domains_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def organization_move_users(request: HttpRequest, organization_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    organization = get_object_or_404(Organization, pk=organization_id)
    ids = _parse_id_list(request.POST, "user_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one user.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for uid in ids:
                if direction == "add":
                    DataOwnershipContext(uid).enable_or_assign_organization(
                        actor=actor, organization_id=organization.pk,
                    )
                else:
                    row = UserOrganization.objects.get(user_id=uid, organization_id=organization.pk)
                    DataOwnershipContext(uid).disable_organization_assignment(
                        actor=actor, user_organization_id=row.pk,
                    )
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    user_assignments = list(
        UserOrganization.objects.filter(organization=organization, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    users_assigned = [ua.user for ua in user_assignments]
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    msg = "Users assigned." if direction == "add" else "Users removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "organizational/organizations/_users_dlb_only.html", {
        "organization": organization,
        "users_available": users_available,
        "users_assigned": users_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def organization_delete(request: HttpRequest, organization_id: int) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    organization = get_object_or_404(Organization, pk=organization_id)
    name = organization.name
    try:
        organization.delete()
        messages.success(request, f"Organization '{name}' deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete organization: {exc}")
        return redirect(reverse("organization_detail", kwargs={"organization_id": organization.pk}))
    return redirect(reverse("organization_index"))
