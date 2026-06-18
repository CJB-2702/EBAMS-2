"""Snapshot user data domain ids and Django permissions into the session at login."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser
    from django.http import HttpRequest

SESSION_KEY_DOMAIN_IDS = "user_domain_ids"
SESSION_KEY_PERMISSION_CODENAMES = "user_permission_codenames"


def refresh_auth_in_session(request: HttpRequest, user: AbstractBaseUser) -> None:
    """Store active data domain ids and effective permission strings on the session."""
    from django.contrib.auth.models import AnonymousUser

    if not getattr(user, "is_active", True) or isinstance(user, AnonymousUser):
        request.session.pop(SESSION_KEY_DOMAIN_IDS, None)
        request.session.pop(SESSION_KEY_PERMISSION_CODENAMES, None)
        return

    domain_ids = list(user.get_all_domain_ids())
    perms = sorted(user.get_all_permissions())
    request.session[SESSION_KEY_DOMAIN_IDS] = domain_ids
    request.session[SESSION_KEY_PERMISSION_CODENAMES] = perms


def session_domain_ids(request: HttpRequest) -> list[int]:
    """Data domain primary keys from the last login snapshot, or []."""
    raw = request.session.get(SESSION_KEY_DOMAIN_IDS)
    if raw is None:
        return []
    return list(raw)


def session_permission_codenames(request: HttpRequest) -> frozenset[str]:
    """Effective Django permission strings from the last login snapshot, or empty."""
    raw = request.session.get(SESSION_KEY_PERMISSION_CODENAMES)
    if raw is None:
        return frozenset()
    return frozenset(raw)


from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def _on_user_logged_in(sender, request, user, **kwargs):
    """Automatically refresh auth snapshot when any user logs in."""
    refresh_auth_in_session(request, user)
