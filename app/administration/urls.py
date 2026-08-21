from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from app.administration.presentation_layer.entrypoints.data_access.domain_organizations import (
    domain_organizations_portal,
)
from app.administration.presentation_layer.entrypoints.data_access.domain_templates import (
    domain_template_create,
    domain_template_delete,
    domain_template_detail,
    domain_template_edit,
    domain_template_index,
    domain_template_move_domains,
)
from app.administration.presentation_layer.entrypoints.data_access.domains import (
    domain_create,
    domain_delete,
    domain_detail,
    domain_edit,
    domain_index,
    domain_move_organizations,
    domain_move_users,
)
from app.administration.presentation_layer.entrypoints.index import administration_index
from app.administration.presentation_layer.entrypoints.organizational.divisions import (
    division_create,
    division_delete,
    division_detail,
    division_edit,
    division_index,
    division_move_organizations,
    division_move_users,
)
from app.administration.presentation_layer.entrypoints.organizational.organizations import (
    organization_create,
    organization_delete,
    organization_detail,
    organization_edit,
    organization_index,
    organization_move_domains,
    organization_move_users,
)
from app.administration.presentation_layer.entrypoints.permissions.permission_groups import (
    permission_group_create,
    permission_group_delete,
    permission_group_detail,
    permission_group_edit,
    permission_group_index,
    permission_group_move_permissions,
    permission_group_move_users,
)
from app.administration.presentation_layer.entrypoints.permissions.permissions import (
    permission_detail,
    permission_index,
)
from app.administration.presentation_layer.entrypoints.permissions.roles import (
    role_create,
    role_delete,
    role_detail,
    role_edit,
    role_index,
    role_move_permission_groups,
    role_move_users,
)
from app.administration.presentation_layer.entrypoints.users.users import (
    check_direct_permissions_against_group,
    user_detail,
    user_edit,
    user_index,
    user_move_roles,
    user_move_groups,
    user_move_permissions,
    user_move_divisions,
    user_move_organizations,
    user_move_domains,
)

urlpatterns = [
    path("", administration_index, name="administration_index"),
    path("login/", LoginView.as_view(template_name="adm_login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # User Management
    path("users/", user_index, name="user_index"),
    path("users/<int:user_id>/", user_detail, name="user_detail"),
    path("users/<int:user_id>/edit/", user_edit, name="user_edit"),
    path(
        "users/<int:user_id>/edit/check-direct-permissions/",
        check_direct_permissions_against_group,
        name="check_direct_permissions_against_group",
    ),
    path("users/<int:user_id>/move-roles/", user_move_roles, name="user_move_roles"),
    path("users/<int:user_id>/move-groups/", user_move_groups, name="user_move_groups"),
    path("users/<int:user_id>/move-permissions/", user_move_permissions, name="user_move_permissions"),
    path("users/<int:user_id>/move-divisions/", user_move_divisions, name="user_move_divisions"),
    path("users/<int:user_id>/move-organizations/", user_move_organizations, name="user_move_organizations"),
    path("users/<int:user_id>/move-domains/", user_move_domains, name="user_move_domains"),

    # Organizational Assignments
    path("organizations/", organization_index, name="organization_index"),
    path("organizations/new/", organization_create, name="organization_create"),
    path("organizations/<int:organization_id>/", organization_detail, name="organization_detail"),
    path("organizations/<int:organization_id>/edit/", organization_edit, name="organization_edit"),
    path("organizations/<int:organization_id>/delete/", organization_delete, name="organization_delete"),
    path("organizations/<int:organization_id>/move-domains/", organization_move_domains, name="organization_move_domains"),
    path("organizations/<int:organization_id>/move-users/", organization_move_users, name="organization_move_users"),

    path("divisions/", division_index, name="division_index"),
    path("divisions/new/", division_create, name="division_create"),
    path("divisions/<int:division_id>/", division_detail, name="division_detail"),
    path("divisions/<int:division_id>/edit/", division_edit, name="division_edit"),
    path("divisions/<int:division_id>/delete/", division_delete, name="division_delete"),
    path("divisions/<int:division_id>/move-organizations/", division_move_organizations, name="division_move_organizations"),
    path("divisions/<int:division_id>/move-users/", division_move_users, name="division_move_users"),

    # Permissions System
    path("permissions/", permission_index, name="permission_index"),
    path("permissions/<int:permission_id>/", permission_detail, name="permission_detail"),

    path("permission-groups/", permission_group_index, name="permission_group_index"),
    path("permission-groups/new/", permission_group_create, name="permission_group_create"),
    path("permission-groups/<int:group_id>/", permission_group_detail, name="permission_group_detail"),
    path("permission-groups/<int:group_id>/edit/", permission_group_edit, name="permission_group_edit"),
    path("permission-groups/<int:group_id>/delete/", permission_group_delete, name="permission_group_delete"),
    path("permission-groups/<int:group_id>/move-permissions/", permission_group_move_permissions, name="permission_group_move_permissions"),
    path("permission-groups/<int:group_id>/move-users/", permission_group_move_users, name="permission_group_move_users"),

    path("roles/", role_index, name="role_index"),
    path("roles/new/", role_create, name="role_create"),
    path("roles/<slug:role_slug>/", role_detail, name="role_detail"),
    path("roles/<slug:role_slug>/edit/", role_edit, name="role_edit"),
    path("roles/<slug:role_slug>/delete/", role_delete, name="role_delete"),
    path("roles/<slug:role_slug>/move-permission-groups/", role_move_permission_groups, name="role_move_permission_groups"),
    path("roles/<slug:role_slug>/move-users/", role_move_users, name="role_move_users"),

    # Data Access
    path("domains/", domain_index, name="domain_index"),
    path("domains/new/", domain_create, name="domain_create"),
    path("domains/<int:domain_id>/", domain_detail, name="domain_detail"),
    path("domains/<int:domain_id>/edit/", domain_edit, name="domain_edit"),
    path("domains/<int:domain_id>/delete/", domain_delete, name="domain_delete"),
    path("domains/<int:domain_id>/move-organizations/", domain_move_organizations, name="domain_move_organizations"),
    path("domains/<int:domain_id>/move-users/", domain_move_users, name="domain_move_users"),

    path("domain-templates/", domain_template_index, name="domain_template_index"),
    path("domain-templates/new/", domain_template_create, name="domain_template_create"),
    path("domain-templates/<slug:template_slug>/", domain_template_detail, name="domain_template_detail"),
    path("domain-templates/<slug:template_slug>/edit/", domain_template_edit, name="domain_template_edit"),
    path("domain-templates/<slug:template_slug>/delete/", domain_template_delete, name="domain_template_delete"),
    path("domain-templates/<slug:template_slug>/move-domains/", domain_template_move_domains, name="domain_template_move_domains"),

    path("domain-organizations/", domain_organizations_portal, name="domain_organizations_portal"),

    # Events / Audit Portal
    path("events/", lambda req: _events_portal(req, "administration"), name="administration_events_portal"),
]

def _events_portal(request, default_type: str):
    from app.events.presentation_layer.entrypoints.events import event_index
    get_copy = request.GET.copy()
    if not get_copy.get("event_type"):
        get_copy["event_type"] = default_type
    request.GET = get_copy
    return event_index(request)
