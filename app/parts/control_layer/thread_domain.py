"""thread_domain — resolves the bootstrap Domain id for an activity thread.

ActivityThread rows require a NOT-NULL ``domain`` (the shared ``event`` table's
domain FK), but parts entities carry no single ownership domain of their own
(D14: ``is_domain_limited`` + ``PartDomainAccessMapping`` govern access, never
``thread.domain`` — see the ``ActivityThread`` docstring and BUILD_BRIEF §1/§2).

So a part thread must still write *something* into that column. Rather than an
opaque shared ``SYSTEM`` catch-all, each functional thread variant gets one
default ``Domain`` named after its own class/type — the throwaway value then
self-documents what kind of thread it is. The rule is generic:
``default domain = the thread's own class/type name``.

This is purely "what to physically write into the NOT NULL column"; it is not
access control.
"""

from __future__ import annotations

from app.administration.models import Domain
from app.events.models import Event
from app.events.models.event import ActivityThreadType

# One default Domain per functional thread variant, keyed by thread_type.
# (name, slug) — get_or_create by slug so it stays idempotent across seeds and
# full DB resets.
_DEFAULT_DOMAIN_SPECS: dict[str, tuple[str, str]] = {
    ActivityThreadType.EVENT: ("Event", "event"),
    ActivityThreadType.DOCUMENTATION: ("Activity Thread", "activity-thread"),
    ActivityThreadType.PHOTO_GALLERY: ("File Set", "file-set"),
}


def _resolve_thread_type(thread_cls_or_type) -> str:
    """Accept a thread_type string, an Event/proxy instance, or an Event/proxy
    class, and return the ``ActivityThreadType`` value identifying its variant."""
    if isinstance(thread_cls_or_type, str):
        return thread_cls_or_type
    if isinstance(thread_cls_or_type, Event):
        # An existing row — prefer its own type, fall back to the class default.
        return thread_cls_or_type.thread_type or thread_cls_or_type._DEFAULT_THREAD_TYPE
    if isinstance(thread_cls_or_type, type) and issubclass(thread_cls_or_type, Event):
        return thread_cls_or_type._DEFAULT_THREAD_TYPE
    raise TypeError(f"Cannot resolve a thread type from {thread_cls_or_type!r}.")


def ensure_default_domains() -> None:
    """Idempotently create every variant's default Domain. Called from seeding."""
    for name, slug in _DEFAULT_DOMAIN_SPECS.values():
        Domain.objects.get_or_create(slug=slug, defaults={"name": name})


def default_domain_id_for(thread_cls_or_type) -> int:
    """Return the id of the default bootstrap Domain for a thread variant,
    creating it on first use so callers never depend on seed ordering."""
    thread_type = _resolve_thread_type(thread_cls_or_type)
    try:
        name, slug = _DEFAULT_DOMAIN_SPECS[thread_type]
    except KeyError as exc:
        raise KeyError(
            f"No default domain configured for thread type {thread_type!r}."
        ) from exc
    domain, _ = Domain.objects.get_or_create(slug=slug, defaults={"name": name})
    return domain.id
