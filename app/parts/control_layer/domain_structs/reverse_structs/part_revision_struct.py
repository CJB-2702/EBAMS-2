"""PartRevisionStruct — read model for a single revision plus its thread's
comments and documents."""

from __future__ import annotations

from app.parts.models import PartRevision


class PartRevisionNotFoundError(Exception):
    pass


class PartRevisionStruct:
    def __init__(self, revision_id: int) -> None:
        self.revision_id = revision_id
        try:
            self.revision: PartRevision = PartRevision.objects.select_related(
                "part", "thread"
            ).get(id=revision_id)
        except PartRevision.DoesNotExist as exc:
            raise PartRevisionNotFoundError(
                f"PartRevision {revision_id} not found."
            ) from exc

    def to_dict(self) -> dict:
        from app.parts.control_layer.managers.part_thread_manager import (
            PartThreadManager,
        )

        rev = self.revision
        thread_manager = PartThreadManager(rev)
        return {
            "id": rev.id,
            "sequence": rev.sequence,
            "major": rev.major_revision_number,
            "minor": rev.minor_revision_number,
            "major_name": rev.major_revision_name,
            "minor_name": rev.minor_revision_name,
            "status": rev.status,
            "date_of_release": rev.date_of_release,
            "summary": rev.summary,
            "notes": rev.notes,
            "documents": thread_manager.documents(),
            "comments": thread_manager.comments(),
        }
