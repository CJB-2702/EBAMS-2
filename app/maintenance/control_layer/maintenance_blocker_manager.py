"""Manager: blockers sub-domain for one MaintenanceDetail
(MaintenanceContext.blocker_manager).

Owns MaintenanceBlocker creation/resolution and keeps MaintenanceDetail.status
in sync — opening a blocker moves the event to Blocked; resolving the last
active blocker returns it to In Progress.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.events.models.event import EventStatus, EventPriority
from app.maintenance.models.blocker import (
    BlockerPriority,
    BlockerReason,
    MaintenanceBlocker,
)


class MaintenanceBlockerNarrator:
    """Narrator: the machine-written activity-log sentences for blockers.

    Separated from the manager so the wording is changeable in one place and
    testable without opening a blocker.
    """

    @staticmethod
    def created(*, actor, reason: str, billable_hours_lost: float | None) -> str:
        who = getattr(actor, "username", None) or "system"
        lost = (
            f" Estimated {billable_hours_lost} billable hour(s) lost."
            if billable_hours_lost
            else ""
        )
        return f"Work placed in blocked status by {who}: {reason}.{lost}"

    @staticmethod
    def resolved(
        *, actor, reason: str, resolution_notes: str, billable_hours_lost=None
    ) -> str:
        who = getattr(actor, "username", None) or "system"
        lost = (
            f" {billable_hours_lost} billable hour(s) lost."
            if billable_hours_lost
            else ""
        )
        return f"Blocker resolved by {who} ({reason}): {resolution_notes}{lost}"


class MaintenanceBlockerManager:
    def __init__(self, maintenance_context) -> None:
        self._ctx = maintenance_context

    @property
    def active_blockers(self) -> list[MaintenanceBlocker]:
        return self._ctx.struct.active_blockers

    def add_blocker(
        self,
        *,
        reason: str,
        notes: str = "",
        start_date=None,
        billable_hours_lost: float | None = None,
        priority: str = BlockerPriority.MEDIUM,
        expected_resolution_date=None,
        event_priority: str | None = None,
        comment: str = "",
        actor=None,
    ) -> MaintenanceBlocker:
        """Open a blocker.

        Only one active blocker per event at a time — a second cannot be opened
        while the first is unresolved.

        Three things beyond the row itself happen here, because in the legacy
        app they were part of the same act and splitting them left the record
        incomplete:

        * `event_priority` — discovering a blocker is usually the moment the
          job's urgency changes, so the form that captures the blocker is the
          form that re-prioritises the event.
        * `comment` — every blocker lands in the event's activity log. If the
          caller supplies text it is recorded as a human comment; if not, a
          machine-written one is generated, so the log never has a silent gap
          where work stopped.
        * `billable_hours_lost` — the cost of the stoppage, captured at the
          moment someone knows it rather than reconstructed later.
        """
        if reason not in BlockerReason.values:
            raise ValueError(
                f"'{reason}' is not a valid blocker reason. "
                f"Choose one of: {', '.join(BlockerReason.values)}."
            )
        if billable_hours_lost is not None and billable_hours_lost < 0:
            raise ValueError("Billable hours lost cannot be negative.")
        if self.active_blockers:
            raise ValueError(
                "An active blocker already exists. Resolve it before adding another."
            )

        detail = self._ctx.maintenance_detail
        with transaction.atomic():
            blocker = MaintenanceBlocker.objects.create(
                maintenance_detail=detail,
                reason=reason,
                notes=notes,
                start_date=start_date or timezone.now(),
                billable_hours_lost=billable_hours_lost,
                priority=priority,
                expected_resolution_date=expected_resolution_date,
                created_by=actor,
                updated_by=actor,
            )

            update_fields: list[str] = []
            if detail.status in (EventStatus.PLANNED, EventStatus.IN_PROGRESS):
                detail.status = EventStatus.BLOCKED
                update_fields.append("status")
                if notes:
                    detail.blocker_notes = notes
                    update_fields.append("blocker_notes")
            if event_priority:
                if event_priority not in EventPriority.values:
                    raise ValueError(f"'{event_priority}' is not a valid event priority.")
                detail.priority = event_priority
                update_fields.append("priority")
            if update_fields:
                detail.updated_by = actor
                detail.save(update_fields=update_fields + ["updated_by", "updated_at"])

        self._narrate(
            comment=comment,
            fallback=MaintenanceBlockerNarrator.created(
                actor=actor,
                reason=reason,
                billable_hours_lost=billable_hours_lost,
            ),
            actor=actor,
        )
        self._ctx.refresh()
        return blocker

    def _narrate(self, *, comment: str, fallback: str, actor) -> None:
        """Write the activity-log entry for a blocker transition.

        Deliberately outside the transaction above: a comment failing to save
        must not roll back the blocker itself. The blocker is the record that
        matters; the narration is commentary on it.
        """
        text = (comment or "").strip()
        self._ctx.add_comment(
            {"content": text or fallback},
            actor=actor,
            is_human_made=bool(text),
        )

    def end_blocker(
        self,
        *,
        blocker_id: int,
        resolution_notes: str,
        start_date=None,
        end_date=None,
        billable_hours_lost: float | None = None,
        notes: str | None = None,
        comment: str = "",
        actor=None,
    ) -> MaintenanceBlocker:
        """Resolve a blocker — the close-out form, not just a status flip.

        Closing is when the facts are actually known, so this is where they
        get corrected, matching the legacy "End Blocked Status" form:

        * `start_date` — the blocker was usually opened some time after work
          actually stopped, so the start is editable on the way out.
        * `end_date` — when it ended, which is frequently not "now" (the
          technician logs it after the fact, or schedules a known future end).
        * `billable_hours_lost` — the real cost. At open it is a guess; here
          it is a measurement, so a value supplied now overwrites the estimate.
        * `notes` — amend the description of the stoppage itself.
        * `resolution_notes` — mandatory. A blocker is a claim that work could
          not proceed; clearing it silently leaves no record of what changed.
        """
        if not (resolution_notes or "").strip():
            raise ValueError("A resolution note is required to resolve a blocker.")
        if billable_hours_lost is not None and billable_hours_lost < 0:
            raise ValueError("Billable hours lost cannot be negative.")

        blocker = MaintenanceBlocker.objects.get(
            pk=blocker_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        if blocker.end_date is not None:
            return blocker

        final_start = start_date or blocker.start_date
        final_end = end_date or timezone.now()
        if final_start and final_end < final_start:
            raise ValueError("A blocker cannot end before it started.")

        detail = self._ctx.maintenance_detail
        with transaction.atomic():
            blocker.start_date = final_start
            blocker.end_date = final_end
            blocker.resolution_notes = resolution_notes.strip()
            if billable_hours_lost is not None:
                blocker.billable_hours_lost = billable_hours_lost
            if notes is not None and notes.strip():
                blocker.notes = notes.strip()
            blocker.updated_by = actor
            blocker.save(
                update_fields=[
                    "start_date", "end_date", "resolution_notes",
                    "billable_hours_lost", "notes", "updated_by", "updated_at",
                ]
            )

            remaining = (
                MaintenanceBlocker.objects.filter(
                    maintenance_detail_id=self._ctx.maintenance_detail_id,
                    end_date__isnull=True,
                    deleted_at__isnull=True,
                )
                .exclude(pk=blocker_id)
                .exists()
            )
            if not remaining and detail.status == EventStatus.BLOCKED:
                detail.status = EventStatus.IN_PROGRESS
                detail.updated_by = actor
                detail.save(update_fields=["status", "updated_by", "updated_at"])

        self._narrate(
            comment=comment,
            fallback=MaintenanceBlockerNarrator.resolved(
                actor=actor,
                reason=blocker.reason,
                resolution_notes=resolution_notes,
                billable_hours_lost=blocker.billable_hours_lost,
            ),
            actor=actor,
        )
        self._ctx.refresh()
        return blocker

    def update_blocker(self, *, blocker_id: int, actor=None, **fields) -> MaintenanceBlocker:
        if fields.get("reason") is not None and fields["reason"] not in BlockerReason.values:
            raise ValueError(f"'{fields['reason']}' is not a valid blocker reason.")
        blocker = MaintenanceBlocker.objects.get(
            pk=blocker_id, maintenance_detail_id=self._ctx.maintenance_detail_id
        )
        update_fields: list[str] = []
        for field_name in (
            "reason",
            "notes",
            "start_date",
            "billable_hours_lost",
            "priority",
            "expected_resolution_date",
        ):
            if field_name in fields and fields[field_name] is not None:
                setattr(blocker, field_name, fields[field_name])
                update_fields.append(field_name)
        if update_fields:
            blocker.updated_by = actor
            update_fields += ["updated_by", "updated_at"]
            blocker.save(update_fields=update_fields)
        self._ctx.refresh()
        return blocker
