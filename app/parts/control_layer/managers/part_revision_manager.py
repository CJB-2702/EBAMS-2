"""PartRevisionManager — the only writer of PartRevision rows. Owns the numeric
allocation rules (D4) so major/minor can never be set by hand inconsistently."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.db import transaction

from app.parts.control_layer.narrators.part_activity_narrator import PartActivityNarrator
from app.parts.control_layer.narrators.part_revision_narrator import (
    PartRevisionNarrator,
)
from app.parts.models import Part, PartRevision, PartRevisionStatus

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class PartRevisionManager:
    def __init__(self, part: Part, actor: "AbstractUser | None" = None) -> None:
        self.part = part
        self.actor = actor

    def release_major(
        self,
        *,
        summary: str = "",
        major_name: str | None = None,
        date_of_release: datetime.date | None = None,
        status: str = PartRevisionStatus.DRAFT,
    ) -> PartRevision:
        with transaction.atomic():
            existing = PartRevision.objects.select_for_update().filter(part=self.part)
            next_major = self._max(existing, "major_revision_number") + 1
            next_sequence = self._max(existing, "sequence") + 1
            revision = PartRevision.objects.create(
                part=self.part,
                sequence=next_sequence,
                date_of_release=date_of_release or datetime.date.today(),
                major_revision_number=next_major,
                minor_revision_number=0,
                major_revision_name=major_name,
                status=status,
                summary=summary,
                created_by=self.actor,
                updated_by=self.actor,
            )
            PartActivityNarrator.for_revision(revision, self.actor).record(
                PartRevisionNarrator.major_released(self.part, revision)
            )
        return revision

    def redline(
        self,
        *,
        major_number: int | None = None,
        minor_name: str | None = None,
        summary: str = "",
        date_of_release: datetime.date | None = None,
    ) -> PartRevision:
        with transaction.atomic():
            existing = PartRevision.objects.select_for_update().filter(part=self.part)
            target_major = major_number or self._max(existing, "major_revision_number")
            next_minor = (
                self._max(existing.filter(major_revision_number=target_major), "minor_revision_number")
                + 1
            )
            next_sequence = self._max(existing, "sequence") + 1
            revision = PartRevision.objects.create(
                part=self.part,
                sequence=next_sequence,
                date_of_release=date_of_release or datetime.date.today(),
                major_revision_number=target_major,
                minor_revision_number=next_minor,
                minor_revision_name=minor_name,
                status=PartRevisionStatus.REDLINE,
                summary=summary,
                created_by=self.actor,
                updated_by=self.actor,
            )
            PartActivityNarrator.for_revision(revision, self.actor).record(
                PartRevisionNarrator.redline_issued(self.part, revision)
            )
        return revision

    def update(self, revision_id: int, *, data: dict) -> PartRevision:
        revision = PartRevision.objects.select_for_update().get(
            id=revision_id, part=self.part
        )
        revision.major_revision_name = data["major_name"]
        revision.minor_revision_name = data["minor_name"]
        revision.summary = data["summary"]
        revision.notes = data["notes"]
        revision.date_of_release = data["date_of_release"]
        revision.updated_by = self.actor
        revision.save(
            update_fields=[
                "major_revision_name",
                "minor_revision_name",
                "summary",
                "notes",
                "date_of_release",
                "updated_at",
                "updated_by",
            ]
        )
        PartActivityNarrator.for_revision(revision, self.actor).record(
            PartRevisionNarrator.metadata_updated(self.part, revision)
        )
        return revision

    def set_status(self, revision_id: int, status: str) -> PartRevision:
        revision = PartRevision.objects.select_for_update().get(
            id=revision_id, part=self.part
        )
        old_status = revision.status
        revision.status = status
        revision.updated_by = self.actor
        revision.save(update_fields=["status", "updated_at", "updated_by"])
        PartActivityNarrator.for_revision(revision, self.actor).record(
            PartRevisionNarrator.status_changed(self.part, revision, old_status, status)
        )
        return revision

    @staticmethod
    def _max(qs, field: str) -> int:
        value = qs.order_by(f"-{field}").values_list(field, flat=True).first()
        return value or 0
