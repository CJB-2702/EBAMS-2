"""Shared HTTP-form parsing helpers for the parts adapters. Every ``*CreateAdaptor``
cleans ``request.POST`` the same two ways — checkbox truthiness and int-or-None —
so those primitives live here instead of being re-implemented per adapter."""

from __future__ import annotations

#: The values an HTML checkbox / truthy form field may arrive as.
_TRUTHY = ("on", "true", "True", "1")


def parse_checkbox(post, key: str) -> bool:
    """True when ``post[key]`` is one of the standard truthy form values."""
    return post.get(key) in _TRUTHY


def parse_int(value) -> int | None:
    """Coerce a form value to ``int``; blank/None/garbage becomes ``None``."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
