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
    """Comments + attachments thread. Behavior is fixed by the class.

    Domain scoping caveat — inherited `domain` is NOT authoritative here.
    ActivityThread (and the file collection it carries) inherits Event's single,
    NOT-NULL `domain` field. That single-domain model is correct for events with a
    physical, single-domain counterpart (e.g. an asset lives in exactly one domain).
    But when a thread is *tied to another item*, it is subordinate to that item and
    must defer to the owning item's domain-access rules for visibility — it must NOT
    treat its own `domain` value as the source of truth for who may read it.

    The clearest case is a Part definition: a part is a *shared* record that can span
    domains (and may be restricted to a select few via `is_domain_limited` +
    PartDomainAccessMapping). A part's activity thread therefore has no meaningful
    domain of its own — the `domain` set at thread-creation time is an incidental
    bootstrap value (the column is NOT NULL and needs *something*), not an access
    control. Who may see the thread is decided by who may access the Part, i.e. the
    Part's domain mapping — never by this row's `domain`. Any owner that carries its
    own domain-access model should be treated the same way.
    """

    _THREAD_TYPES = frozenset({ActivityThreadType.DOCUMENTATION})
    _DEFAULT_THREAD_TYPE = ActivityThreadType.DOCUMENTATION
    _ALLOW_COMMENTS = True
    _ALLOW_DIRECT_ATTACHMENTS = True
    _SENTINEL_FIELDS = (("title", _THREAD_SENTINEL), ("event_type", _THREAD_SENTINEL))

    objects = FamilyThreadManager()  # ActivityThread.objects → documentation rows only

    class Meta:
        proxy = True
