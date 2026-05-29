"""Read-only query helpers for the events presentation layer."""

from __future__ import annotations

from django.db.models import QuerySet

from app.events.models import Comment, Event


def list_events_for_user(user) -> QuerySet:
    """All active events visible to the user, newest first."""
    return (
        Event.objects.visible_to(user)
        .select_related("domain", "created_by")
        .order_by("-created_at")
    )


def list_comments_for_event(event: Event, include_shadow: bool = False) -> QuerySet:
    """
    Active comments for an event.
    By default returns only human-authored comments.
    Pass include_shadow=True to also include visible machine comments.
    """
    qs = Comment.objects.active().filter(event=event).select_related("created_by")
    if not include_shadow:
        qs = qs.human()
    return qs.order_by("created_at")


def list_all_comments_for_event(event: Event) -> QuerySet:
    """All comments including soft-deleted ones. For privileged views only."""
    return (
        Comment.objects.filter(event=event)
        .select_related("created_by")
        .order_by("created_at", "revision")
    )
