"""safe_next_url — validate a caller-supplied ``next`` redirect target."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.http import url_has_allowed_host_and_scheme

if TYPE_CHECKING:
    from django.http import HttpRequest


def safe_next_url(request: "HttpRequest", fallback: str) -> str:
    """Return ``next`` from POST or GET when it is a safe same-host URL,
    otherwise ``fallback``."""
    nxt = (request.POST.get("next") or request.GET.get("next") or "").strip()
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return fallback
