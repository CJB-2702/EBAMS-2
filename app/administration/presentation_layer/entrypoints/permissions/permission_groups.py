"""Permission groups (auth.Group): list / detail / edit / create / delete."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    assert_actor_may_add_groups,
    assert_actor_may_add_permissions,
    assert_actor_may_remove_groups,
    assert_actor_may_remove_permissions,
    assert_can_manage_target,
    is_admin_actor,
    is_grant_actor,
)
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()


def _require_admin(request: HttpRequest) -> HttpResponse | None:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_admin or Django superusers may modify permission groups.",
        )
    return None


def _require_grant(request: HttpRequest) -> HttpResponse | None:
    if not is_grant_actor(request.user):
        return HttpResponseForbidden(
            "Only generic_manager, generic_admin, or superusers may change permission group membership.",
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


@require_http_methods(["GET"])
def permission_group_index(request: HttpRequest) -> HttpResponse:
    q = request.GET.get("q", "").strip()
    qs = Group.objects.order_by("name").annotate(
        permission_count=Count("permissions", distinct=True),
        user_count=Count("user", distinct=True),
    )
    if q:
        qs = qs.filter(name__icontains=q)
    return render(
        request,
        "permissions/permission_groups/index.html",
        {
            "groups": qs,
            "q": q,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def permission_group_create(request: HttpRequest) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Permission group name is required.")
            return render(request, "permissions/permission_groups/new.html", {"name": name})
        if Group.objects.filter(name=name).exists():
            messages.error(request, f"A permission group named '{name}' already exists.")
            return render(request, "permissions/permission_groups/new.html", {"name": name})
        group = Group.objects.create(name=name)
        messages.success(request, f"Permission group '{group.name}' created.")
        return redirect(reverse("permission_group_detail", kwargs={"group_id": group.pk}))

    return render(request, "permissions/permission_groups/new.html", {})


@require_http_methods(["GET"])
def permission_group_detail(request: HttpRequest, group_id: int) -> HttpResponse:
    group = get_object_or_404(
        Group.objects.prefetch_related("permissions__content_type"),
        pk=group_id,
    )
    permissions = group.permissions.select_related("content_type").order_by(
        "content_type__app_label",
        "content_type__model",
        "codename",
    )
    members = User.objects.filter(groups=group).order_by("username").distinct()
    return render(
        request,
        "permissions/permission_groups/detail.html",
        {
            "group": group,
            "permissions": permissions,
            "members": members,
            "can_edit": is_admin_actor(request.user),
        },
    )


@require_http_methods(["GET", "POST"])
def permission_group_edit(request: HttpRequest, group_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    group = get_object_or_404(
        Group.objects.prefetch_related("permissions__content_type"),
        pk=group_id,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        actor = request.user
        try:
            if action == "rename_group":
                if not is_admin_actor(actor):
                    return HttpResponseForbidden("Admin only.")
                name = request.POST.get("name", "").strip()
                if not name:
                    messages.error(request, "Permission group name is required.")
                elif name != group.name and Group.objects.filter(name=name).exists():
                    messages.error(request, f"A permission group named '{name}' already exists.")
                else:
                    group.name = name
                    group.save()
                    messages.success(request, "Permission group renamed.")
            elif action == "add_permissions":
                ids = _parse_id_list(request.POST, "permission_ids")
                if not ids:
                    messages.error(request, "Select at least one permission.")
                else:
                    perms = list(
                        Permission.objects.select_related("content_type").filter(pk__in=ids),
                    )
                    assert_actor_may_add_permissions(actor, permissions_to_add=perms)
                    with transaction.atomic():
                        group.permissions.add(*perms)
                    messages.success(request, "Permissions added to group.")
            elif action == "remove_permissions":
                ids = _parse_id_list(request.POST, "permission_ids")
                if not ids:
                    messages.error(request, "Select at least one permission.")
                else:
                    perms = list(
                        Permission.objects.select_related("content_type").filter(pk__in=ids),
                    )
                    assert_actor_may_remove_permissions(actor, permissions_to_remove=perms)
                    with transaction.atomic():
                        group.permissions.remove(*perms)
                    messages.success(request, "Permissions removed from group.")
            elif action == "add_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            target = User.objects.get(pk=uid)
                            assert_can_manage_target(actor, target)
                            assert_actor_may_add_groups(actor, groups_to_add=[group])
                            target.groups.add(group)
                    messages.success(request, "Users added to group.")
            elif action == "remove_users":
                ids = _parse_id_list(request.POST, "user_ids")
                if not ids:
                    messages.error(request, "Select at least one user.")
                else:
                    with transaction.atomic():
                        for uid in ids:
                            target = User.objects.get(pk=uid)
                            assert_can_manage_target(actor, target)
                            assert_actor_may_remove_groups(actor, groups_to_remove=[group])
                            target.groups.remove(group)
                    messages.success(request, "Users removed from group.")
            else:
                messages.error(request, "Unknown action.")
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        return redirect(reverse("permission_group_edit", kwargs={"group_id": group.pk}))

    permissions_assigned = list(
        group.permissions.select_related("content_type").order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        ),
    )
    assigned_perm_ids = {p.pk for p in permissions_assigned}
    permissions_available = list(
        Permission.objects.select_related("content_type")
        .exclude(pk__in=assigned_perm_ids)
        .order_by("content_type__app_label", "content_type__model", "codename"),
    )
    members = list(User.objects.filter(groups=group).order_by("username").distinct())
    member_ids = {m.pk for m in members}
    users_available = list(list_users_ordered().exclude(pk__in=member_ids))

    return render(
        request,
        "permissions/permission_groups/edit.html",
        {
            "group": group,
            "permissions_assigned": permissions_assigned,
            "permissions_available": permissions_available,
            "users_assigned": members,
            "users_available": users_available,
            "can_rename": is_admin_actor(request.user),
        },
    )


@require_http_methods(["POST"])
def permission_group_move_permissions(request: HttpRequest, group_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    group = get_object_or_404(Group.objects.prefetch_related("permissions__content_type"), pk=group_id)
    ids = _parse_id_list(request.POST, "permission_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one permission.", status=400)

    try:
        perms = list(Permission.objects.select_related("content_type").filter(pk__in=ids))
        if direction == "add":
            assert_actor_may_add_permissions(request.user, permissions_to_add=perms)
            with transaction.atomic():
                group.permissions.add(*perms)
        else:
            assert_actor_may_remove_permissions(request.user, permissions_to_remove=perms)
            with transaction.atomic():
                group.permissions.remove(*perms)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    group.refresh_from_db()
    permissions_assigned = list(
        group.permissions.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model", "codename",
        ),
    )
    assigned_perm_ids = {p.pk for p in permissions_assigned}
    permissions_available = list(
        Permission.objects.select_related("content_type")
        .exclude(pk__in=assigned_perm_ids)
        .order_by("content_type__app_label", "content_type__model", "codename"),
    )

    msg = "Permissions added to group." if direction == "add" else "Permissions removed from group."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "permissions/permission_groups/_permissions_dlb_only.html", {
        "group": group,
        "permissions_available": permissions_available,
        "permissions_assigned": permissions_assigned,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def permission_group_move_users(request: HttpRequest, group_id: int) -> HttpResponse:
    denied = _require_grant(request)
    if denied is not None:
        return denied

    group = get_object_or_404(Group, pk=group_id)
    ids = _parse_id_list(request.POST, "user_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one user.", status=400)

    try:
        with transaction.atomic():
            for uid in ids:
                target = User.objects.get(pk=uid)
                assert_can_manage_target(request.user, target)
                if direction == "add":
                    assert_actor_may_add_groups(request.user, groups_to_add=[group])
                    target.groups.add(group)
                else:
                    assert_actor_may_remove_groups(request.user, groups_to_remove=[group])
                    target.groups.remove(group)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    members = list(User.objects.filter(groups=group).order_by("username").distinct())
    member_ids = {m.pk for m in members}
    users_available = list(list_users_ordered().exclude(pk__in=member_ids))

    msg = "Users added to group." if direction == "add" else "Users removed from group."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "permissions/permission_groups/_users_dlb_only.html", {
        "group": group,
        "users_available": users_available,
        "users_assigned": members,
    }).content.decode("utf-8")
    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def permission_group_delete(request: HttpRequest, group_id: int) -> HttpResponse:
    denied = _require_admin(request)
    if denied is not None:
        return denied
    group = get_object_or_404(Group, pk=group_id)
    name = group.name
    try:
        group.delete()
        messages.success(request, f"Permission group '{name}' deleted.")
    except Exception as exc:
        messages.error(request, f"Could not delete permission group: {exc}")
        return redirect(reverse("permission_group_detail", kwargs={"group_id": group.pk}))
    return redirect(reverse("permission_group_index"))
