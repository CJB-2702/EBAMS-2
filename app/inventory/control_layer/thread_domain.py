"""thread_domain — resolves the bootstrap Domain id for an inventory thread.

Two callers today:

  FileSet          the Room/RoomLocation layout gallery.
  ActivityThread   the IntakeSession comment/attachment thread
                   (intake_portal_workflow.md §8).

Event-family rows require a NOT-NULL `domain`, but neither owner carries a
single ownership domain of its own. A Room/RoomLocation defers to its
Warehouse's `domains` M2M; an IntakeSession spans every shipment it receives
against, and those shipments may sit in different domains. The bootstrap
Domain is purely "what to physically write into the NOT NULL column"; it is
NOT access control. Who may read an intake session's thread is decided by
who may read the session.

Mirrors `app/assets/control_layer/thread_domain.py` / `app/parts/control_layer/thread_domain.py`.
"""

from __future__ import annotations

from app.administration.models import Domain
from app.events.models import ActivityThread, Event, FileSet

_DEFAULT_DOMAIN_SPECS: dict[type, tuple[str, str]] = {
    FileSet: ("File Set", "file-set"),
    ActivityThread: ("Activity Thread", "activity-thread"),
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
