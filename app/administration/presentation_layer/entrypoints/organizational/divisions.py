"""Divisions: list / detail / edit / create / delete entrypoints."""

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
    Organization,
    UserDivision,
)
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify divisions.",
        )
    return None


def _require_grant(request: HttpRequest) -> HttpResponse | None:
    if not is_grant_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_manager, generic_admin, or superusers may change division assignments.",
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
    base = slugify(name) or "division"
    slug = base
    i = 2
    while Division.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


@require_http_methods(["GET"])
def division_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Division.objects.order_by("name").annotate(
        organization_count=Count("organizations", distinct=True),
    )
    if q:
        qs = qs.filter(name__icontains=q)
    return render(
        request,
        "organizational/divisions/index.html",
        {
            "divisions": qs,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def division_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Division name is required.")
            return render(
                request,
                "organizational/divisions/new.html",
                {"name": name},
            )
        division = Division.objects.create(
            name=name,
            slug=_unique_slug(name),
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Division '{division.name}' created.")
        return redirect(reverse("division_detail", kwargs={"division_id": division.pk}))

    return render(request, "organizational/divisions/new.html", {})


@require_http_methods(["GET"])
def division_detail(request: HttpRequest, division_id: int) -> HttpResponse:
    division = get_object_or_404(Division, pk=division_id)
    organizations = division.organizations.order_by("name")
    user_assignments = (
        UserDivision.objects.filter(division=division, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "organizational/divisions/detail.html",
        {
            "division": division,
            "organizations": organizations,
            "user_assignments": user_assignments,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def division_edit(request: HttpRequest, division_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    division = get_object_or_404(Division, pk=division_id)

    if request.method == "POST":
        action = request.POST.get("action", "")
        actor = request.user
        try:
            if action == "update_metadata":
                if not is_admin_actor(actor):
                    return HttpResponseForbidden("Admin only.")
                name = request.POST.get("name", "").strip()
                if name:
                    division.name = name
                    division.updated_by = actor
                    division.save(update_fields=["name", "updated_at", "updated_by"])
                    messages.success(request, "Division updated.")
            elif action == "add_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                if not ids:
                    messages.error(request, "Select at least one organization.")
                else:
                    with transaction.atomic():
                        for oid in ids:
                            link_organization_to_division(
                                actor=actor,
                                organization_id=oid,
                                division_id=division.pk,
                            )
                    messages.success(request, "Organizations linked.")
            elif action == "remove_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                if not ids:
                    messages.error(request, "Select at least one organization.")
                else:
                    with transaction.atomic():
                        for oid in ids:
                            unlink_organization_from_division(
                                actor=actor,
                                organization_id=oid,
                                division_id=division.pk,
                            )
                    messages.success(request, "Organizations removed.")
            elif action == "add_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            DataOwnershipContext(uid).enable_or_assign_division(
                                actor=actor,
                                division_id=division.pk,
                            )
                    messages.success(request, "Users assigned.")
            elif action == "remove_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            row = UserDivision.objects.get(
                                user_id=uid,
                                division_id=division.pk,
                            )
                            DataOwnershipContext(uid).disable_division_assignment(
                                actor=actor,
                                user_division_id=row.pk,
                            )
                    messages.success(request, "Users removed.")
            else:
                messages.error(request, "Unknown action.")
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("division_edit", kwargs={"division_id": division.pk}))

    organizations_assigned = list(division.organizations.order_by("name"))
    assigned_org_ids = {o.pk for o in organizations_assigned}
    organizations_available = list(
        Organization.objects.exclude(pk__in=assigned_org_ids).order_by("name"),
    )

    user_assignments = list(
        UserDivision.objects.filter(division=division, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_assigned = [ua.user for ua in user_assignments]
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    return render(
        request,
        "organizational/divisions/edit.html",
        {
            "division": division,
            "organizations_assigned": organizations_assigned,
            "organizations_available": organizations_available,
            "users_assigned": users_assigned,
            "users_available": users_available,
        },
    )


@require_http_methods(["POST"])
def division_move_organizations(request: HttpRequest, division_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    division = get_object_or_404(Division, pk=division_id)
    ids = _parse_id_list(request.POST, "organization_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one organization.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for oid in ids:
                if direction == "add":
                    link_organization_to_division(actor=actor, organization_id=oid, division_id=division.pk)
                else:
                    unlink_organization_from_division(actor=actor, organization_id=oid, division_id=division.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    organizations_assigned = list(division.organizations.order_by("name"))
    assigned_org_ids = {o.pk for o in organizations_assigned}
    organizations_available = list(Organization.objects.exclude(pk__in=assigned_org_ids).order_by("name"))

    msg = "Organizations linked." if direction == "add" else "Organizations removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "organizational/divisions/_organizations_dlb_only.html", {
        "division": division,
        "organizations_available": organizations_available,
        "organizations_assigned": organizations_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def division_move_users(request: HttpRequest, division_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    division = get_object_or_404(Division, pk=division_id)
    ids = _parse_id_list(request.POST, "user_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one user.", status=400)

    try:
        actor = request.user
        with transaction.atomic():
            for uid in ids:
                if direction == "add":
                    DataOwnershipContext(uid).enable_or_assign_division(actor=actor, division_id=division.pk)
                else:
                    row = UserDivision.objects.get(user_id=uid, division_id=division.pk)
                    DataOwnershipContext(uid).disable_division_assignment(actor=actor, user_division_id=row.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    user_assignments = list(
        UserDivision.objects.filter(division=division, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    users_assigned = [ua.user for ua in user_assignments]
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    msg = "Users assigned." if direction == "add" else "Users removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "organizational/divisions/_users_dlb_only.html", {
        "division": division,
        "users_available": users_available,
        "users_assigned": users_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def division_delete(request: HttpRequest, division_id: int) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    division = get_object_or_404(Division, pk=division_id)
    name = division.name
    try:
        division.delete()
        messages.success(request, f"Division '{name}' deleted.")
    except Exception as exc:  # PROTECT FK or other DB constraint
        messages.error(request, f"Could not delete division: {exc}")
        return redirect(reverse("division_detail", kwargs={"division_id": division.pk}))
    return redirect(reverse("division_index"))
