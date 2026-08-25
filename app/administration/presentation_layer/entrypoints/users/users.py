"""User management: list / detail / edit / create."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from app.administration.control_layer.data_ownership.data_ownership_context import (
    DataOwnershipContext,
)
from app.administration.control_layer.data_ownership.user_domain_assignment_context import (
    UserDomainAssignmentContext,
)
from app.administration.control_layer.permissions.django_permissions_context import (
    DjangoPermissionsContext,
)
from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    is_admin_actor,
)
from app.administration.control_layer.permissions.user_role_assignment_context import (
    UserRoleAssignmentContext,
)
from app.administration.models import (
    Division,
    Domain,
    DomainTemplate,
    Organization,
    Role,
    UserDivision,
    UserDomain,
    UserDomainTemplate,
    UserOrganization,
    UserRole,
)
from app.administration.presentation_layer.search.domain_warnings import (
    compute_domain_warnings,
    serialize_warnings,
)
from app.administration.presentation_layer.search.user_access import (
    load_user_data_ownership_struct,
    load_user_django_permissions_struct,
)
from app.administration.presentation_layer.search.users import list_users_ordered

User = get_user_model()

CHECK_DIRECT_PERMS_GROUP_NOTICE = (
    "Some selected permissions may be automatically inherited by the user based off of "
    "assigned groups, refer to the below list before committing"
)

TAB_PARTIAL_MAP = {
    "information": "users/_edit_information.html",
    "permissions": "users/_edit_permissions.html",
    "data-access": "users/_edit_data_access.html",
}
DEFAULT_TAB_VIEW = "information"


def _parse_id_list(post, key: str) -> list[int]:
    out: list[int] = []
    for raw in post.getlist(key):
        try:
            out.append(int(raw))
        except ValueError:
            continue
    return out


@require_http_methods(["GET", "POST"])
def user_create(request: HttpRequest) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only Django superusers or members of the generic_admin group may access this page.",
        )

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        errors = []
        if not username:
            errors.append("Username is required.")
        elif User.objects.filter(username=username).exists():
            errors.append("A user with this username already exists.")

        if not password:
            errors.append("Password is required.")
        elif password != password_confirm:
            errors.append("Passwords do not match.")
        elif len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        if errors:
            return render(
                request,
                "users/create.html",
                {
                    "username": username,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "errors": errors,
                },
            )

        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            messages.success(request, f"User '{username}' created successfully.")
            return redirect(reverse("user_detail", kwargs={"user_id": user.pk}))
        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")
            return render(
                request,
                "users/create.html",
                {
                    "username": username,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "errors": [str(e)],
                },
            )

    return render(request, "users/create.html", {})


@require_http_methods(["GET"])
def user_index(request: HttpRequest) -> HttpResponse:
    query = request.GET.get("q", "").strip()
    active_filter = request.GET.get("active", "all")
    staff_filter = request.GET.get("staff", "all")
    page_size = 25

    users = list_users_ordered()
    if query:
        users = users.filter(username__icontains=query)
    if active_filter in {"yes", "no"}:
        users = users.filter(is_active=(active_filter == "yes"))
    if staff_filter in {"yes", "no"}:
        users = users.filter(is_staff=(staff_filter == "yes"))

    total_count = users.count()
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    max_page = max(((total_count - 1) // page_size) + 1, 1)
    page = min(page, max_page)
    offset = (page - 1) * page_size
    users = users[offset : offset + page_size]

    return render(
        request,
        "users/index.html",
        {
            "users": users,
            "query": query,
            "active_filter": active_filter,
            "staff_filter": staff_filter,
            "total_count": total_count,
            "page": page,
            "max_page": max_page,
            "page_size": page_size,
        },
    )


@require_http_methods(["GET"])
def user_detail(request: HttpRequest, user_id: int) -> HttpResponse:
    target = get_object_or_404(
        User.objects.only(
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "date_joined",
        ),
        pk=user_id,
    )

    perm_struct = load_user_django_permissions_struct(target.pk)
    ownership = load_user_data_ownership_struct(target.pk)
    domain_warnings = serialize_warnings(
        compute_domain_warnings(user_id=target.pk, domains=ownership.domains),
    )
    domain_rows = [
        {"domain": d, "warning": domain_warnings.get(d.pk, {"severity": "", "label": ""})}
        for d in ownership.domains
    ]

    role_assignments = (
        UserRole.objects.filter(user=target, is_active=True)
        .select_related("role", "role__parent_role")
        .order_by("role__name")
    )

    try:
        domain_template_assignment = UserDomainTemplate.objects.select_related("template").get(
            user=target,
            is_active=True,
        )
    except UserDomainTemplate.DoesNotExist:
        domain_template_assignment = None

    return render(
        request,
        "users/detail.html",
        {
            "target_user": target,
            "perm_struct": perm_struct,
            "ownership": ownership,
            "domain_rows": domain_rows,
            "role_assignments": role_assignments,
            "domain_template_assignment": domain_template_assignment,
            "show_edit_link": is_admin_actor(request.user),
        },
    )


@require_http_methods(["POST"])
def check_direct_permissions_against_group(
    request: HttpRequest,
    user_id: int,
) -> HttpResponse:
    """HTML fragment (HTMX): which selected perms are already inherited via groups."""
    if not is_admin_actor(request.user):
        return HttpResponseForbidden("Forbidden")

    target = get_object_or_404(User.objects.only("pk"), pk=user_id)
    permission_ids = _parse_id_list(request.POST, "permission_ids")

    items: list[dict[str, object]] = []
    if permission_ids:
        perms = {
            p.pk: p
            for p in Permission.objects.filter(pk__in=permission_ids).select_related(
                "content_type",
            )
        }
        for pid in permission_ids:
            p = perms.get(pid)
            if p is None:
                continue
            group_names = list(
                target.groups.filter(permissions__id=pid)
                .order_by("name")
                .values_list("name", flat=True)
                .distinct(),
            )
            if not group_names:
                continue
            label = f"{p.content_type.app_label} | {p.content_type.model} | {p.name}"
            items.append({"label": label, "groups": group_names})

    return render(
        request,
        "users/_direct_perm_group_check.html",
        {"message": CHECK_DIRECT_PERMS_GROUP_NOTICE, "items": items},
    )


@require_http_methods(["GET", "POST"])
def user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden(
            "Only Django superusers or members of the generic_admin group may access this page.",
        )

    target = get_object_or_404(
        User.objects.prefetch_related("groups", "user_permissions__content_type"),
        pk=user_id,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "set_password":
                form = SetPasswordForm(user=target, data=request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Password updated.")
                    return redirect(reverse("user_edit", kwargs={"user_id": user_id}))
                messages.error(request, "Correct the errors below.")
                return _render_user_edit(request, target, password_form=form)

            ctx_perm = DjangoPermissionsContext(user_id)
            ctx_own = DataOwnershipContext(user_id)
            ctx_role = UserRoleAssignmentContext(user_id)
            ctx_template = UserDomainAssignmentContext(user_id)
            actor = request.user

            if action == "add_groups":
                ids = _parse_id_list(request.POST, "group_ids")
                if not ids:
                    messages.error(request, "Select at least one group to add.")
                else:
                    try:
                        with transaction.atomic():
                            for gid in ids:
                                ctx_perm.add_group(actor=actor, group_id=gid)
                        messages.success(request, "Group membership updated.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "remove_groups":
                ids = _parse_id_list(request.POST, "group_ids")
                if not ids:
                    messages.error(request, "Select at least one group to remove.")
                else:
                    try:
                        with transaction.atomic():
                            for gid in ids:
                                ctx_perm.remove_group(actor=actor, group_id=gid)
                        messages.success(request, "Group membership updated.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "add_permissions":
                ids = _parse_id_list(request.POST, "permission_ids")
                if not ids:
                    messages.error(request, "Select at least one permission to add.")
                else:
                    try:
                        with transaction.atomic():
                            for pid in ids:
                                ctx_perm.add_direct_permission(actor=actor, permission_id=pid)
                        messages.success(request, "Direct permissions updated.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "remove_permissions":
                ids = _parse_id_list(request.POST, "permission_ids")
                if not ids:
                    messages.error(request, "Select at least one permission to remove.")
                else:
                    try:
                        with transaction.atomic():
                            for pid in ids:
                                ctx_perm.remove_direct_permission(actor=actor, permission_id=pid)
                        messages.success(request, "Direct permissions updated.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "assign_roles":
                ids = _parse_id_list(request.POST, "role_ids")
                if not ids:
                    messages.error(request, "Select at least one role to assign.")
                else:
                    try:
                        with transaction.atomic():
                            for rid in ids:
                                ctx_role.assign_role(actor=actor, role_id=rid)
                        messages.success(request, "Roles assigned.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "remove_roles":
                ids = _parse_id_list(request.POST, "role_ids")
                if not ids:
                    messages.error(request, "Select at least one role to remove.")
                else:
                    try:
                        with transaction.atomic():
                            for rid in ids:
                                ctx_role.remove_role(actor=actor, role_id=rid)
                        messages.success(request, "Roles removed.")
                    except GrantPermissionDenied as exc:
                        messages.error(request, str(exc))
            elif action == "update_role_relationship":
                role_id = int(request.POST.get("role_id", "0"))
                relationship = request.POST.get("relationship_type", "primary").strip()
                ctx_role.update_relationship_type(
                    actor=actor,
                    role_id=role_id,
                    relationship_type=relationship,
                )
                messages.success(request, "Role relationship updated.")
            elif action == "update_role_notes":
                role_id = int(request.POST.get("role_id", "0"))
                notes = request.POST.get("notes", "")
                ctx_role.update_notes(actor=actor, role_id=role_id, notes=notes)
                messages.success(request, "Role notes updated.")
            elif action == "assign_divisions":
                ids = _parse_id_list(request.POST, "division_ids")
                with transaction.atomic():
                    for did in ids:
                        ctx_own.enable_or_assign_division(actor=actor, division_id=did)
                messages.success(request, "Division assignment updated.")
            elif action == "disable_divisions":
                ids = _parse_id_list(request.POST, "division_ids")
                with transaction.atomic():
                    for did in ids:
                        row = UserDivision.objects.get(user_id=user_id, division_id=did)
                        ctx_own.disable_division_assignment(actor=actor, user_division_id=row.pk)
                messages.success(request, "Division assignment updated.")
            elif action == "assign_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                with transaction.atomic():
                    for oid in ids:
                        ctx_own.enable_or_assign_organization(actor=actor, organization_id=oid)
                messages.success(request, "Organization assignment updated.")
            elif action == "disable_organizations":
                ids = _parse_id_list(request.POST, "organization_ids")
                with transaction.atomic():
                    for oid in ids:
                        row = UserOrganization.objects.get(user_id=user_id, organization_id=oid)
                        ctx_own.disable_organization_assignment(
                            actor=actor,
                            user_organization_id=row.pk,
                        )
                messages.success(request, "Organization assignment updated.")
            elif action == "assign_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                with transaction.atomic():
                    for did in ids:
                        ctx_own.enable_or_assign_domain(actor=actor, domain_id=did)
                messages.success(request, "Direct data domain assignment updated.")
            elif action == "disable_domains":
                ids = _parse_id_list(request.POST, "domain_ids")
                with transaction.atomic():
                    for did in ids:
                        row = UserDomain.objects.get(user_id=user_id, domain_id=did)
                        ctx_own.disable_domain_assignment(actor=actor, user_domain_id=row.pk)
                messages.success(request, "Direct data domain assignment updated.")
            elif action == "assign_domain_template":
                template_id_raw = request.POST.get("template_id", "").strip()
                additive = request.POST.get("additive") == "1"
                if not template_id_raw.isdigit():
                    messages.error(request, "Select a domain template.")
                else:
                    ctx_template.assign_domain_template(
                        actor=actor,
                        template_id=int(template_id_raw),
                        additive=additive,
                    )
                    mode = "additive" if additive else "rebase"
                    messages.success(request, f"Domain template assigned ({mode}).")
            elif action == "rebase_domain_template":
                row = ctx_template.re_rebase_current(actor=actor)
                if row is None:
                    messages.error(request, "User has no active domain template to rebase.")
                else:
                    messages.success(request, "Domain set re-synced to template.")
            elif action == "disable_domain_template":
                row = ctx_template.disable_current(actor=actor)
                if row is None:
                    messages.error(request, "User has no active domain template to disable.")
                else:
                    messages.success(request, "Domain template disabled.")
            else:
                messages.error(request, "Unknown action.")
        except (ObjectDoesNotExist, ValueError) as exc:
            messages.error(request, str(exc))
        except GrantPermissionDenied as exc:
            messages.error(request, str(exc))

        return redirect(reverse("user_edit", kwargs={"user_id": user_id}))

    return _render_user_edit(request, target, password_form=None)


def _render_user_edit(
    request: HttpRequest,
    target,
    *,
    password_form: SetPasswordForm | None,
):
    perm_struct = load_user_django_permissions_struct(target.pk)
    ownership = load_user_data_ownership_struct(target.pk)
    domain_warnings = serialize_warnings(
        compute_domain_warnings(user_id=target.pk, domains=ownership.domains),
    )
    domain_rows = [
        {"domain": d, "warning": domain_warnings.get(d.pk, {"severity": "", "label": ""})}
        for d in ownership.domains
    ]

    assigned_group_ids = list(target.groups.values_list("pk", flat=True))
    groups_available = list(Group.objects.exclude(pk__in=assigned_group_ids).order_by("name"))
    groups_assigned = list(target.groups.order_by("name"))

    direct_ids = list(target.user_permissions.values_list("pk", flat=True))
    permissions_available = list(
        Permission.objects.select_related("content_type")
        .exclude(pk__in=direct_ids)
        .order_by("content_type__app_label", "content_type__model", "codename"),
    )
    permissions_assigned = list(
        target.user_permissions.select_related("content_type").order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        ),
    )
    available_perm_ids = {p.pk for p in permissions_available}
    group_granted_perm_ids = set(
        Permission.objects.filter(group__user=target).values_list("pk", flat=True).distinct(),
    )
    inherited_permission_ids = sorted(available_perm_ids & group_granted_perm_ids)

    role_assignments = list(
        UserRole.objects.filter(user=target, is_active=True)
        .select_related("role", "role__parent_role")
        .order_by("role__name"),
    )
    assigned_role_ids = {ra.role_id for ra in role_assignments}
    roles_available = list(
        Role.objects.filter(is_active=True).exclude(pk__in=assigned_role_ids).order_by("name"),
    )
    roles_assigned_for_listbox = [ra.role for ra in role_assignments]

    assigned_division_ids = [d.pk for d in ownership.divisions]
    divisions_available = list(
        Division.objects.exclude(pk__in=assigned_division_ids).order_by("name"),
    )
    divisions_assigned = ownership.divisions

    assigned_org_ids = [o.pk for o in ownership.organizations]
    organizations_available = list(
        Organization.objects.exclude(pk__in=assigned_org_ids).order_by("name"),
    )
    organizations_assigned = ownership.organizations

    assigned_domain_ids = [d.pk for d in ownership.domains]
    domains_available = list(
        Domain.objects.exclude(pk__in=assigned_domain_ids).order_by("name"),
    )
    domains_assigned = ownership.domains

    available_domain_templates = list(
        DomainTemplate.objects.filter(is_active=True).order_by("name"),
    )
    try:
        current_domain_template_assignment = UserDomainTemplate.objects.select_related(
            "template",
        ).get(user=target, is_active=True)
    except UserDomainTemplate.DoesNotExist:
        current_domain_template_assignment = None

    pwd_form = password_form if password_form is not None else SetPasswordForm(user=target)

    requested_view = request.GET.get("view", DEFAULT_TAB_VIEW)
    active_view = requested_view if requested_view in TAB_PARTIAL_MAP else DEFAULT_TAB_VIEW
    tab_partial = TAB_PARTIAL_MAP[active_view]

    context = {
        "target_user": target,
        "perm_struct": perm_struct,
        "ownership": ownership,
        "domain_rows": domain_rows,
        "role_assignments": role_assignments,
        "roles_assigned_for_listbox": roles_assigned_for_listbox,
        "roles_available": roles_available,
        "available_domain_templates": available_domain_templates,
        "current_domain_template_assignment": current_domain_template_assignment,
        "password_form": pwd_form,
        "groups_available": groups_available,
        "groups_assigned": groups_assigned,
        "permissions_available": permissions_available,
        "permissions_assigned": permissions_assigned,
        "divisions_available": divisions_available,
        "divisions_assigned": divisions_assigned,
        "organizations_available": organizations_available,
        "organizations_assigned": organizations_assigned,
        "domains_available": domains_available,
        "domains_assigned": domains_assigned,
        "inherited_permission_ids": inherited_permission_ids,
        "active_view": active_view,
        "tab_partial": tab_partial,
    }

    # HTMX tab clicks ask for just the partial; full reloads get the whole page.
    if request.headers.get("HX-Request") == "true" and "view" in request.GET:
        return render(request, tab_partial, context)
    return render(request, "users/edit.html", context)


def _render_move_response(
    request: HttpRequest,
    target_user,
    dlb_id: str,
    left_id: str,
    right_id: str,
    template_name: str,
    message_text: str,
    message_type: str = "success",
):
    """
    Render a dual-list-box fragment + alert notification for an HTMX response.
    Used by move endpoints (move-roles, move-groups, etc).
    """
    # Reconstruct the context just for the dlb component.
    # This is fetch-heavy but keeps the handlers small.
    ctx = _render_user_edit(request, target_user, password_form=None)
    ctx_dict = ctx.context if hasattr(ctx, 'context') else ctx

    html = f'''
<div class="notification is-{message_type} is-light dlb-alert" data-dismiss="3000">
  {message_text}
  <button class="delete" aria-label="Dismiss"></button>
</div>

{{% include "{template_name}" %}}
'''
    # Render just the template fragment inline.
    from django.template.loader import render_to_string
    fragment = render_to_string(template_name, ctx_dict)
    return HttpResponse(fragment)


@require_http_methods(["POST"])
def user_move_roles(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "role_ids")
    direction = request.POST.get("direction", "add")  # "add" or "remove"

    if not ids:
        return HttpResponse("Select at least one role.", status=400)

    try:
        ctx = UserRoleAssignmentContext(user_id)
        with transaction.atomic():
            for rid in ids:
                if direction == "add":
                    ctx.assign_role(actor=request.user, role_id=rid)
                else:
                    ctx.remove_role(actor=request.user, role_id=rid)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    # Return fragment.
    perm_struct = load_user_django_permissions_struct(target.pk)
    ownership = load_user_data_ownership_struct(target.pk)

    role_assignments = list(
        UserRole.objects.filter(user=target, is_active=True)
        .select_related("role", "role__parent_role")
        .order_by("role__name"),
    )
    assigned_role_ids = {ra.role_id for ra in role_assignments}
    roles_available = list(
        Role.objects.filter(is_active=True).exclude(pk__in=assigned_role_ids).order_by("name"),
    )
    roles_assigned_for_listbox = [ra.role for ra in role_assignments]

    context = {
        "target_user": target,
        "perm_struct": perm_struct,
        "ownership": ownership,
        "role_assignments": role_assignments,
        "roles_assigned_for_listbox": roles_assigned_for_listbox,
        "roles_available": roles_available,
    }

    msg = "Roles updated." if direction == "add" else "Roles removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_roles_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def user_move_groups(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "group_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one group.", status=400)

    try:
        ctx = DjangoPermissionsContext(user_id)
        with transaction.atomic():
            for gid in ids:
                if direction == "add":
                    ctx.add_group(actor=request.user, group_id=gid)
                else:
                    ctx.remove_group(actor=request.user, group_id=gid)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    assigned_group_ids = list(target.groups.values_list("pk", flat=True))
    groups_available = list(Group.objects.exclude(pk__in=assigned_group_ids).order_by("name"))
    groups_assigned = list(target.groups.order_by("name"))

    context = {
        "target_user": target,
        "groups_available": groups_available,
        "groups_assigned": groups_assigned,
    }

    msg = "Groups updated." if direction == "add" else "Groups removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_groups_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def user_move_permissions(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "permission_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one permission.", status=400)

    try:
        ctx = DjangoPermissionsContext(user_id)
        with transaction.atomic():
            for pid in ids:
                if direction == "add":
                    ctx.add_direct_permission(actor=request.user, permission_id=pid)
                else:
                    ctx.remove_direct_permission(actor=request.user, permission_id=pid)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    direct_ids = list(target.user_permissions.values_list("pk", flat=True))
    permissions_available = list(
        Permission.objects.select_related("content_type")
        .exclude(pk__in=direct_ids)
        .order_by("content_type__app_label", "content_type__model", "codename"),
    )
    permissions_assigned = list(
        target.user_permissions.select_related("content_type").order_by(
            "content_type__app_label",
            "content_type__model",
            "codename",
        ),
    )

    context = {
        "target_user": target,
        "permissions_available": permissions_available,
        "permissions_assigned": permissions_assigned,
    }

    msg = "Permissions updated." if direction == "add" else "Permissions removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_permissions_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def user_move_divisions(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "division_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one division.", status=400)

    try:
        ctx = DataOwnershipContext(user_id)
        with transaction.atomic():
            for did in ids:
                if direction == "add":
                    ctx.enable_or_assign_division(actor=request.user, division_id=did)
                else:
                    row = UserDivision.objects.get(user_id=user_id, division_id=did)
                    ctx.disable_division_assignment(actor=request.user, user_division_id=row.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    ownership = load_user_data_ownership_struct(target.pk)
    assigned_division_ids = [d.pk for d in ownership.divisions]
    divisions_available = list(
        Division.objects.exclude(pk__in=assigned_division_ids).order_by("name"),
    )
    divisions_assigned = ownership.divisions

    context = {
        "target_user": target,
        "divisions_available": divisions_available,
        "divisions_assigned": divisions_assigned,
    }

    msg = "Divisions updated." if direction == "add" else "Divisions removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_divisions_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def user_move_organizations(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "organization_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one organization.", status=400)

    try:
        ctx = DataOwnershipContext(user_id)
        with transaction.atomic():
            for oid in ids:
                if direction == "add":
                    ctx.enable_or_assign_organization(actor=request.user, organization_id=oid)
                else:
                    row = UserOrganization.objects.get(user_id=user_id, organization_id=oid)
                    ctx.disable_organization_assignment(
                        actor=request.user,
                        user_organization_id=row.pk,
                    )
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    ownership = load_user_data_ownership_struct(target.pk)
    assigned_org_ids = [o.pk for o in ownership.organizations]
    organizations_available = list(
        Organization.objects.exclude(pk__in=assigned_org_ids).order_by("name"),
    )
    organizations_assigned = ownership.organizations

    context = {
        "target_user": target,
        "organizations_available": organizations_available,
        "organizations_assigned": organizations_assigned,
    }

    msg = "Organizations updated." if direction == "add" else "Organizations removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_organizations_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)


@require_http_methods(["POST"])
def user_move_domains(request: HttpRequest, user_id: int) -> HttpResponse:
    if not is_admin_actor(request.user):
        return HttpResponseForbidden()

    target = get_object_or_404(User, pk=user_id)
    ids = _parse_id_list(request.POST, "domain_ids")
    direction = request.POST.get("direction", "add")

    if not ids:
        return HttpResponse("Select at least one domain.", status=400)

    try:
        ctx = DataOwnershipContext(user_id)
        with transaction.atomic():
            for did in ids:
                if direction == "add":
                    ctx.enable_or_assign_domain(actor=request.user, domain_id=did)
                else:
                    row = UserDomain.objects.get(user_id=user_id, domain_id=did)
                    ctx.disable_domain_assignment(actor=request.user, user_domain_id=row.pk)
    except (ObjectDoesNotExist, ValueError, GrantPermissionDenied) as exc:
        return HttpResponse(str(exc), status=400)

    ownership = load_user_data_ownership_struct(target.pk)
    assigned_domain_ids = [d.pk for d in ownership.domains]
    domains_available = list(
        Domain.objects.exclude(pk__in=assigned_domain_ids).order_by("name"),
    )
    domains_assigned = ownership.domains

    context = {
        "target_user": target,
        "domains_available": domains_available,
        "domains_assigned": domains_assigned,
    }

    msg = "Domains updated." if direction == "add" else "Domains removed."
    alert_html = f'<toast-alert type="success" dismiss-delay="3000">{msg}</toast-alert>'
    dlb_html = render(request, "users/_domains_dlb_only.html", context).content.decode('utf-8')

    return HttpResponse(alert_html + dlb_html)
