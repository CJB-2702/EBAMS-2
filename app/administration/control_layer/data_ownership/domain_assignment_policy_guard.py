"""
Policy: who may assign or manage domain templates and domains.

Guard type: **Policy** — authorization gate for domain template and domain assignment flows.
"""

from __future__ import annotations

from django.contrib.auth.models import User

from app.administration.control_layer.permissions.permission_grant_guard import (
    GrantPermissionDenied,
    is_admin_actor,
    is_manager_actor,
)
from app.administration.models import Domain, DomainTemplate


class DomainAccessDenied(GrantPermissionDenied):
    """Raised when an actor lacks permission to perform a domain operation."""
    pass


def assert_actor_may_edit_domain_templates(actor: User) -> None:
    """Only admins may create or edit domain templates."""
    if not is_admin_actor(actor):
        raise DomainAccessDenied(
            "Only generic_admin or Django superusers may edit domain templates.",
        )


def assert_actor_may_assign_domains(
    actor: User,
    *,
    template: DomainTemplate | None = None,
    domains: list[Domain] | None = None,
) -> None:
    """
    Admin always allowed. Managers may assign domains they themselves have access to.

    Checks either a template (domain_template_context) or explicit domains (user_domain_assignment_context).
    """
    if is_admin_actor(actor):
        return

    if not is_manager_actor(actor):
        raise DomainAccessDenied(
            "Only managers or admins may assign domains.",
        )

    if template is not None:
        domain_ids = set(
            template.items.filter(is_active=True).values_list("domain_id", flat=True)
        )
    elif domains:
        domain_ids = {d.pk for d in domains}
    else:
        raise DomainAccessDenied("No domains provided to check.")

    actor_domain_ids = actor.get_all_domain_ids()

    ungranted = domain_ids - actor_domain_ids
    if ungranted:
        raise DomainAccessDenied(
            "Manager may only assign domains they have access to.",
        )
