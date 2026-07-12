"""PartRevisionHistoryStruct — all PartRevision rows for a Part.

Part-scoped collection (constructed from a ``part_id``), distinct from the
singular ``PartRevisionStruct`` (one-revision detail). ``eager_thread`` toggles
per-revision documents/comments: the row list is always eager, but the
per-row thread (the expensive N+1 shape) is loaded only when a caller renders
it — ``part_revisions`` wants it, ``part_detail`` does not (struct plan §3).
"""

from __future__ import annotations

from app.parts.models import PartRevision


class PartRevisionHistoryStruct:
    def __init__(self, part_id: int, *, eager_thread: bool = False) -> None:
        self.part_id = part_id
        self.eager_thread = eager_thread
        self.revisions: list[PartRevision] = list(
            PartRevision.objects.filter(part_id=part_id)
            .select_related("thread")
            .order_by("-major_revision_number", "-minor_revision_number")
        )

    @classmethod
    def from_id(cls, part_id: int, *, eager_thread: bool = False) -> "PartRevisionHistoryStruct":
        return cls(part_id, eager_thread=eager_thread)

    def to_dict(self) -> list[dict]:
        return [self._revision_dict(rev) for rev in self.revisions]

    def _revision_dict(self, rev: PartRevision) -> dict:
        data = {
            "id": rev.id,
            "sequence": rev.sequence,
            "major_revision_number": rev.major_revision_number,
            "minor_revision_number": rev.minor_revision_number,
            "major_revision_name": rev.major_revision_name,
            "minor_revision_name": rev.minor_revision_name,
            "status": rev.status,
            "date_of_release": rev.date_of_release,
            "summary": rev.summary,
        }
        if self.eager_thread:
            from app.parts.control_layer.managers.part_thread_manager import (
                PartThreadManager,
            )

            docs = PartThreadManager(rev).documents()
            data["image_documents"] = [d for d in docs if d["is_image"]]
            data["other_documents"] = [d for d in docs if not d["is_image"]]
            data["comments"] = PartThreadManager(rev).comments()
        return data
