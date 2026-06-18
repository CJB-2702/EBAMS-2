"""FileSet proxy — attachments-only threads (comments disabled).

One of three semantic surface classes over the shared `event` table:

    Event          — event columns + comments + attachments
    ActivityThread — comments + attachments, no event columns
    FileSet        — attachments only, comments disabled              ← this file

A photo gallery is just a FileSet: the behavior (a set of files, no discussion)
drives the name. The class chosen at creation dictates behavior — callers never
pass capability flags. FileSet always disables comments and allows direct
attachments. Behavior is enforced in Event.save(); this file only declares the
contract. The DB row is identical to an Event row (proxy adds no columns).

To add a new attachments-only surface, add its thread_type to ActivityThreadType
and to _THREAD_TYPES below — no new class or migration of capability flags needed.

See docs/Activity_Surfaces.md for use cases and differences.
"""

from __future__ import annotations

from app.events.models.event import (
    ActivityThreadType,
    Event,
    FamilyThreadManager,
    _THREAD_SENTINEL,
)


class FileSet(Event):
    """Attachments-only thread. Comments are off by construction."""

    _THREAD_TYPES = frozenset({ActivityThreadType.PHOTO_GALLERY})
    _DEFAULT_THREAD_TYPE = ActivityThreadType.PHOTO_GALLERY
    _ALLOW_COMMENTS = False
    _ALLOW_DIRECT_ATTACHMENTS = True
    _SENTINEL_FIELDS = (("title", _THREAD_SENTINEL), ("event_type", _THREAD_SENTINEL))

    objects = FamilyThreadManager()  # FileSet.objects → file-set rows only

    class Meta:
        proxy = True
