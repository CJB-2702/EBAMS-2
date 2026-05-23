"""Roles: list / detail / edit / create / delete entrypoints."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    is_admin_actor,
)
from app.administration.control_layer.permissions.role_context import RoleContext
from app.administration.control_layer.permissions.user_role_assignment_context import (
    UserRoleAssignmentContext,
)
from app.administration.models import Role, RoleItem, UserRole
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify roles.",
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
    base = slugify(name) or "role"
    slug = base
    i = 2
    while Role.objects.filter(slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


@require_http_methods(["GET"])
def role_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = (
        Role.objects.order_by("name")
        .select_related("parent_role")
        .annotate(
            item_count=Count("items", distinct=True),
            user_count=Count(
                "user_assignment_links",
                filter=Q(user_assignment_links__is_active=True),
                distinct=True,
            ),
        )
    )
    if q:
        qs = qs.filter(name__icontains=q)
    base_roles = [r for r in qs if r.parent_role_id is None]
    specialized_roles = [r for r in qs if r.parent_role_id is not None]
    return render(
        request,
        "permissions/roles/index.html",
        {
            "base_roles": base_roles,
            "specialized_roles": specialized_roles,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def role_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    parent_options = Role.objects.filter(
        parent_role__isnull=True,
        is_active=True,
    ).order_by("name")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        parent_role_id_raw = request.POST.get("parent_role_id", "").strip()

        if not name:
            messages.error(request, "Role name is required.")
            return render(
                request,
                "permissions/roles/new.html",
                {
                    "name": name,
                    "description": description,
                    "parent_role_id": parent_role_id_raw,
                    "parent_options": parent_options,
                },
            )

        parent_role = None
        if parent_role_id_raw:
            try:
                parent_role = Role.objects.get(pk=int(parent_role_id_raw))
                if parent_role.parent_role_id is not None:
                    messages.error(
                        request,
                        "Specialized roles cannot be parents (single-layer inheritance only).",
                    )
                    return render(
                        request,
                        "permissions/roles/new.html",
                        {
                            "name": name,
                            "description": description,
                            "parent_role_id": parent_role_id_raw,
                            "parent_options": parent_options,
                        },
                    )
            except (Role.DoesNotExist, ValueError):
                messages.error(request, "Invalid parent role.")
                parent_role = None

        role = Role.objects.create(
            name=name,
            slug=_unique_slug(name),
            description=description,
            parent_role=parent_role,
            is_active=True,
            created_by=request.user,
            updated_by=request.user,
        )
        messages.success(request, f"Role '{role.name}' created.")
        return redirect(reverse("role_detail", kwargs={"role_slug": role.slug}))

    return render(
        request,
        "permissions/roles/new.html",
        {"parent_options": parent_options},
    )


@require_http_methods(["GET"])
def role_detail(request: HttpRequest, role_slug: str) -> HttpResponse:
    role = get_object_or_404(Role.objects.select_related("parent_role"), slug=role_slug)
    own_group_ids = RoleItem.objects.filter(role=role).values_list(
        "permission_group_id",
        flat=True,
    )
    permission_groups = Group.objects.filter(pk__in=own_group_ids).order_by("name")
    parent_groups: list[Group] = []
    if role.parent_role:
        parent_group_ids = RoleItem.objects.filter(role=role.parent_role).values_list(
            "permission_group_id",
            flat=True,
        )
        parent_groups = list(
            Group.objects.filter(pk__in=parent_group_ids).order_by("name"),
        )
    child_roles = role.child_roles.filter(is_active=True).order_by("name")
    assignees = (
        UserRole.objects.filter(role=role, is_active=True)
        .select_related("user")
        .order_by("user__username")
    )
    return render(
        request,
        "permissions/roles/detail.html",
        {
            "role": role,
            "permission_groups": permission_groups,
            "parent_groups": parent_groups,
            "child_roles": child_roles,
            "assignees": assignees,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def role_edit(request: HttpRequest, role_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    role = get_object_or_404(Role.objects.select_related("parent_role"), slug=role_slug)

    if request.method == "POST":
        action = request.POST.get("action", "")
        actor = request.user
        ctx = RoleContext(role.pk)
        try:
            if action == "update_metadata":
                name = request.POST.get("name", "").strip() or None
                description = request.POST.get("description", "")
                ctx.update_metadata(actor=actor, name=name, description=description)
                messages.success(request, "Role updated.")
            elif action == "set_active":
                is_active = request.POST.get("is_active") == "1"
                ctx.set_active(actor=actor, is_active=is_active)
                messages.success(
                    request,
                    "Role activated." if is_active else "Role deactivated.",
                )
            elif action == "set_parent_role":
                parent_role_id_raw = request.POST.get("parent_role_id", "").strip()
                if parent_role_id_raw:
                    parent_role_id = int(parent_role_id_raw)
                    parent = Role.objects.get(pk=parent_role_id)
                    if parent.parent_role_id is not None:
                        messages.error(
                            request,
                            "Specialized roles cannot be parents (single-layer inheritance only).",
                        )
                    elif role.child_roles.exists():
                        messages.error(
                            request,
                            "This role has child roles, so it cannot itself become a child role.",
                        )
                    elif parent.pk == role.pk:
                        messages.error(request, "Role cannot be its own parent.")
                    else:
                        ctx.set_parent_role(actor=actor, parent_role_id=parent_role_id)
                        messages.success(request, "Parent role updated.")
                else:
                    ctx.set_parent_role(actor=actor, parent_role_id=None)
                    messages.success(request, "Parent role cleared.")
            elif action == "add_permission_groups":
                ids = _parse_id_list(request.POST, "permission_group_ids")
                if not ids:
                    messages.error(request, "Select at least one permission group.")
                else:
                    with transaction.atomic():
                        for gid in ids:
                            ctx.add_permission_group(actor=actor, group_id=gid)
                    messages.success(request, "Permission groups added to role.")
            elif action == "remove_permission_groups":
                ids = _parse_id_list(request.POST, "permission_group_ids")
                if not ids:
                    messages.error(request, "Select at least one permission group.")
                else:
                    with transaction.atomic():
                        for gid in ids:
                            ctx.remove_permission_group(actor=actor, group_id=gid)
                    messages.success(request, "Permission groups removed from role.")
            elif action == "add_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            UserRoleAssignmentContext(uid).assign_role(
                                actor=actor,
                                role_id=role.pk,
                            )
                    messages.success(request, "Users assigned to role.")
            elif action == "remove_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            UserRoleAssignmentContext(uid).remove_role(
                                actor=actor,
                                role_id=role.pk,
                            )
                    messages.success(request, "Users removed from role.")
            else:
                messages.error(request, "Unknown action.")
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("role_edit", kwargs={"role_slug": role.slug}))

    own_group_ids = list(
        RoleItem.objects.filter(role=role).values_list("permission_group_id", flat=True),
    )
    permission_groups_assigned = list(
        Group.objects.filter(pk__in=own_group_ids).order_by("name"),
    )
    assigned_group_ids = set(own_group_ids)
    permission_groups_available = list(
        Group.objects.exclude(pk__in=assigned_group_ids).order_by("name"),
    )

    parent_role_options = (
        Role.objects.filter(parent_role__isnull=True, is_active=True)
        .exclude(pk=role.pk)
        .order_by("name")
    )

    user_assignments = list(
        UserRole.objects.filter(role=role, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_assigned = [ua.user for ua in user_assignments]
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    return render(
        request,
        "permissions/roles/edit.html",
        {
            "role": role,
            "permission_groups_assigned": permission_groups_assigned,
            "permission_groups_available": permission_groups_available,
            "parent_role_options": parent_role_options,
            "users_assigned": users_assigned,
            "users_available": users_available,
            "has_child_roles": role.child_roles.exists(),
        },
    )


@require_http_methods(["POST"])
def role_move_permission_groups(request: HttpRequest, role_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    role = get_object_or_404(Role.objects.select_related("parent_role"), slug=role_slug)
    ids = _parse_id_list(request.POST, "permission_group_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one permission group.", status=400)

    try:
        ctx = RoleContext(role.pk)
        with transaction.atomic():
            for gid in ids:
                if direction == "add":
                    ctx.add_permission_group(actor=request.user, group_id=gid)
                else:
                    ctx.remove_permission_group(actor=request.user, group_id=gid)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    own_group_ids = list(RoleItem.objects.filter(role=role).values_list("permission_group_id", flat=True))
    permission_groups_assigned = list(Group.objects.filter(pk__in=own_group_ids).order_by("name"))
    permission_groups_available = list(Group.objects.exclude(pk__in=own_group_ids).order_by("name"))

    msg = "Permission groups added." if direction == "add" else "Permission groups removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "permissions/roles/_permission_groups_dlb_only.html", {
        "role": role,
        "permission_groups_available": permission_groups_available,
        "permission_groups_assigned": permission_groups_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def role_move_users(request: HttpRequest, role_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    role = get_object_or_404(Role, slug=role_slug)
    ids = _parse_id_list(request.POST, "user_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one user.", status=400)

    try:
        with transaction.atomic():
            for uid in ids:
                if direction == "add":
                    UserRoleAssignmentContext(uid).assign_role(actor=request.user, role_id=role.pk)
                else:
                    UserRoleAssignmentContext(uid).remove_role(actor=request.user, role_id=role.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    user_assignments = list(
        UserRole.objects.filter(role=role, is_active=True)
        .select_related("user")
        .order_by("user__username"),
    )
    users_assigned = [ua.user for ua in user_assignments]
    assigned_user_ids = {ua.user_id for ua in user_assignments}
    users_available = list(list_users_ordered().exclude(pk__in=assigned_user_ids))

    msg = "Users assigned to role." if direction == "add" else "Users removed from role."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "permissions/roles/_users_dlb_only.html", {
        "role": role,
        "users_available": users_available,
        "users_assigned": users_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def role_delete(request: HttpRequest, role_slug: str) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    role = get_object_or_404(Role, slug=role_slug)
    name = role.name
    try:
        role.delete()
        messages.success(request, f"Role '{name}' deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete role: {exc}")
        return redirect(reverse("role_detail", kwargs={"role_slug": role.slug}))
    return redirect(reverse("role_index"))
