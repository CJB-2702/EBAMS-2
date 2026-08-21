"""One helper so every intake caller gets the SAME configured thread manager.

`IntakeSession.activity_thread` is a nullable OneToOne created lazily on first
write (intake_portal_workflow.md §8), exactly like Part, PartRevision,
SupplierItem and DispatchExpense. `events.ActivityThreadManager` already owns
that mechanics — lazy creation with a bootstrap domain, comments, attachments
— and sub-apps must not hand-roll their own. This module exists only to bind
the two constructor kwargs intake needs, in one place, so a caller cannot get
`thread_attr` wrong and silently write onto nothing.

The bootstrap domain is incidental (see `thread_domain.py`): an intake session
spans every shipment it receives against, and those may sit in different
domains, so the thread has no meaningful domain of its own. Who may read the
thread is decided by who may read the session — never by that column.
"""

from __future__ import annotations

from app.events.control_layer.managers.activity_thread_manager import (
    ActivityThreadManager,
)
from app.events.models import ActivityThread
from app.inventory.control_layer.thread_domain import default_domain_id_for


def session_thread(session, actor=None) -> ActivityThreadManager:
    return ActivityThreadManager(
        session,
        actor,
        thread_attr="activity_thread",
        domain_id_resolver=lambda: default_domain_id_for(ActivityThread),
    )
