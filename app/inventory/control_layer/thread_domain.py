"""thread_domain — resolves the bootstrap Domain id for a Room/RoomLocation
layout gallery thread.

Event-family rows (`FileSet`) require a NOT-NULL `domain`, but a Room or
RoomLocation carries no single ownership domain of its own (a Warehouse's
`domains` M2M governs data-domain scope, never `thread.domain`). The
bootstrap Domain is purely "what to physically write into the NOT NULL
column"; it is not access control.

Mirrors `app/assets/control_layer/thread_domain.py` / `app/parts/control_layer/thread_domain.py`.
"""

from __future__ import annotations

from app.administration.models import Domain
from app.events.models import Event, FileSet

_DEFAULT_DOMAIN_SPECS: dict[type, tuple[str, str]] = {
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
