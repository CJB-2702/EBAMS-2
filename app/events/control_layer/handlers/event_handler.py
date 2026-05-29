"""EventHandler — all create/edit writes for Event rows."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.events.models import (
    ActivityThreadType,
    Comment,
    Event,
    EventPriority,
    EventStatus,
    EventType,
    PRIORITY_CLEARING_STATUSES,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@dataclass
class EventResult:
    ok: bool
    event: Event | None = None
    errors: list[str] = field(default_factory=list)


class EventHandler:
    """Handles all state-changing operations on Event rows."""

    CONTENT_FIELDS = ("title", "description", "event_type", "status", "priority", "event_start", "event_end")
    MACHINE_COMMENT_FIELDS = {"status", "event_start", "event_end"}

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    def create(self, post_data) -> EventResult:
        errors = self._validate_create(post_data)
        if errors:
            return EventResult(ok=False, errors=errors)

        with transaction.atomic():
            event = Event.objects.create(
                thread_type=ActivityThreadType.EVENT,
                allow_comments=True,
                allow_direct_attachments=True,
                domain_id=post_data.get("domain_id"),
                title=post_data.get("title", "").strip(),
                description=post_data.get("description", "").strip(),
                event_type=post_data.get("event_type", EventType.GENERIC),
                status=post_data.get("status", EventStatus.PLANNED),
                priority=post_data.get("priority") or None,
                event_start=post_data.get("event_start") or None,
                event_end=post_data.get("event_end") or None,
                created_by=self.actor,
                updated_by=self.actor,
            )
        return EventResult(ok=True, event=event)

    def edit(self, event: Event, post_data) -> EventResult:
        errors = self._validate_edit(event, post_data)
        if errors:
            return EventResult(ok=False, event=event, errors=errors)

        new_values = self._extract_fields(post_data)
        changes = self._diff(event, new_values)

        if not changes:
            return EventResult(ok=True, event=event)

        with transaction.atomic():
            self._apply_shadow_comment(event, changes)

            changed_fields = {c["field"] for c in changes}
            if changed_fields & self.MACHINE_COMMENT_FIELDS:
                self._apply_machine_comment(event, changes)

            self._apply_field_updates(event, new_values)

        return EventResult(ok=True, event=event)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _validate_create(self, post_data) -> list[str]:
        errors: list[str] = []
        if not post_data.get("title", "").strip():
            errors.append("Title is required.")
        if not post_data.get("domain_id"):
            errors.append("Domain is required.")
        event_type = post_data.get("event_type", "")
        if event_type and event_type not in EventType.values:
            errors.append("Invalid event type.")
        return errors

    def _validate_edit(self, event: Event, post_data) -> list[str]:
        errors: list[str] = []
        if "title" in post_data and not post_data["title"].strip():
            errors.append("Title cannot be blank.")
        start = post_data.get("event_start")
        end = post_data.get("event_end")
        if start and end and end < start:
            errors.append("Event end must be on or after event start.")
        return errors

    def _extract_fields(self, post_data) -> dict:
        return {
            "title": post_data.get("title", "").strip(),
            "description": post_data.get("description", "").strip(),
            "event_type": post_data.get("event_type", ""),
            "status": post_data.get("status", ""),
            "priority": post_data.get("priority") or None,
            "event_start": post_data.get("event_start") or None,
            "event_end": post_data.get("event_end") or None,
        }

    def _diff(self, event: Event, new_values: dict) -> list[dict]:
        changes = []
        field_map = {
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "status": event.status,
            "priority": event.priority,
            "event_start": str(event.event_start) if event.event_start else None,
            "event_end": str(event.event_end) if event.event_end else None,
        }
        for fname, old_val in field_map.items():
            new_val = new_values.get(fname)
            if isinstance(new_val, str):
                new_val = new_val or None
            if str(old_val) != str(new_val):
                changes.append({"field": fname, "from": old_val, "to": new_val})
        return changes

    def _apply_shadow_comment(self, event: Event, changes: list[dict]) -> None:
        """Full field diff — soft-deleted at creation, invisible in the timeline."""
        payload = json.dumps({
            "changed_by": self.actor.username,
            "changed_at": timezone.now().isoformat(),
            "changes": changes,
        })
        now = timezone.now()
        Comment.objects.create(
            activity_thread=event,
            content=payload,
            is_human_made=False,
            deleted_at=now,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def _apply_machine_comment(self, event: Event, changes: list[dict]) -> None:
        """Visible machine comment for notable state transitions (status, times)."""
        notable = [c for c in changes if c["field"] in self.MACHINE_COMMENT_FIELDS]
        parts = []
        for c in notable:
            parts.append(f"{c['field'].replace('_', ' ').title()} changed from '{c['from']}' to '{c['to']}'")
        message = "; ".join(parts)
        Comment.objects.create(
            activity_thread=event,
            content=message,
            is_human_made=False,
            deleted_at=None,
            revision=1,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def _apply_field_updates(self, event: Event, new_values: dict) -> None:
        for fname, val in new_values.items():
            setattr(event, fname, val)

        new_status = new_values.get("status", event.status)
        if new_status in PRIORITY_CLEARING_STATUSES:
            event.priority = None

        event.updated_by = self.actor
        event.save()
