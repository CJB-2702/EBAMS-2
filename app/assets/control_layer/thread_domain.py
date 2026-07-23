"""thread_domain — resolves the bootstrap Domain id for an asset-model thread.

Event-family rows (ActivityThread, FileSet) require a NOT-NULL ``domain`` (the
shared ``event`` table's domain FK), but an AssetModel carries no single ownership
domain of its own — it is a shared product definition that can span domains (its
``domains`` M2M governs association, never ``thread.domain``; see the
``ActivityThread`` docstring).

So a model thread must still write *something* into that column. Rather than an
opaque shared catch-all, each functional thread variant gets one default
``Domain`` named after its own type — the throwaway value then self-documents what
kind of thread it is. This is purely "what to physically write into the NOT NULL
column"; it is not access control.

Mirrors ``app/parts/control_layer/thread_domain.py``.
"""

from __future__ import annotations

from app.administration.models import Domain
from app.events.models import ActivityThread, Event, FileSet

# One default Domain per functional thread variant, keyed by proxy class.
# (name, slug) — get_or_create by slug so it stays idempotent across seeds and
# full DB resets.
_DEFAULT_DOMAIN_SPECS: dict[type, tuple[str, str]] = {
    ActivityThread: ("Activity Thread", "activity-thread"),
    FileSet: ("File Set", "file-set"),
}


def default_domain_id_for(thread_cls: type[Event]) -> int:
    """Return the id of the default bootstrap Domain for a thread variant,
    creating it on first use so callers never depend on seed ordering."""
    try:
        name, slug = _DEFAULT_DOMAIN_SPECS[thread_cls]
    except KeyError as exc:
        raise KeyError(
            f"No default domain configured for thread class {thread_cls!r}."
        ) from exc
    domain, _ = Domain.objects.get_or_create(slug=slug, defaults={"name": name})
    return domain.id
