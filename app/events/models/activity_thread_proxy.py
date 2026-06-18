"""ActivityThread proxy — commentable, attachable non-event threads.

One of three semantic surface classes over the shared `event` table:

    Event          — event columns + comments + attachments
    ActivityThread — comments + attachments, no event columns        ← this file
    FileSet        — attachments only, comments disabled

The class chosen at creation dictates behavior — callers never pass capability
flags. ActivityThread always allows comments and direct attachments. Behavior is
enforced in Event.save(); this file only declares the contract. The DB row is
identical to an Event row (proxy adds no columns); the proxy exists so Comment
and Attachment FKs have a meaningful target and control code gets a correctly
filtered queryset without hand-filtering on thread_type.

See docs/Activity_Surfaces.md for use cases and differences.
"""

from __future__ import annotations

from app.events.models.event import (
    ActivityThreadType,
    Event,
    FamilyThreadManager,
    _THREAD_SENTINEL,
)


class ActivityThread(Event):
    """Comments + attachments thread. Behavior is fixed by the class."""

    _THREAD_TYPES = frozenset({ActivityThreadType.DOCUMENTATION})
    _DEFAULT_THREAD_TYPE = ActivityThreadType.DOCUMENTATION
    _ALLOW_COMMENTS = True
    _ALLOW_DIRECT_ATTACHMENTS = True
    _SENTINEL_FIELDS = (("title", _THREAD_SENTINEL), ("event_type", _THREAD_SENTINEL))

    objects = FamilyThreadManager()  # ActivityThread.objects → documentation rows only

    class Meta:
        proxy = True
