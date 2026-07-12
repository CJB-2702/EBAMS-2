"""RevisionActivityStruct — reverse view from a PartRevision up to its base Part.

Resolves *up* from a revision to the Part it belongs to and gathers both the
revision's own thread and the base Part's activity thread, so a write flow
triggered on a revision can locate the base Part and post to the single Part
audit feed (§5).

Distinct from ``PartRevisionStruct`` (the *downward* single-revision detail
view): this struct exists to answer "which Part does this revision belong to,
and what is its activity feed."
"""

from __future__ import annotations

from app.parts.models import PartRevision


class RevisionActivityNotFoundError(Exception):
    pass


class RevisionActivityStruct:
    def __init__(self, revision_id: int) -> None:
        self.revision_id = revision_id
        try:
            self.revision: PartRevision = PartRevision.objects.select_related(
                "part", "part__documents_thread", "thread"
            ).get(id=revision_id)
        except PartRevision.DoesNotExist as exc:
            raise RevisionActivityNotFoundError(
                f"PartRevision {revision_id} not found."
            ) from exc

    @classmethod
    def from_instance(cls, revision: PartRevision) -> "RevisionActivityStruct":
        struct = cls.__new__(cls)
        struct.revision_id = revision.id
        struct.revision = revision
        return struct

    @property
    def part(self):
        """The base Part this revision belongs to — the machine-comment target."""
        return self.revision.part

    def to_dict(self) -> dict:
        from app.parts.control_layer.managers.part_thread_manager import (
            PartThreadManager,
        )

        rev = self.revision
        part = self.revision.part
        return {
            "revision": {
                "id": rev.id,
                "major": rev.major_revision_number,
                "minor": rev.minor_revision_number,
                "status": rev.status,
            },
            "part": {
                "id": part.id,
                "part_number": part.part_number,
                "name": part.name,
            },
            "revision_thread": {
                "documents": PartThreadManager(rev).documents(),
                "comments": PartThreadManager(rev).comments(),
            },
            "part_thread": {
                "documents": PartThreadManager(
                    part, thread_attr="documents_thread"
                ).documents(),
                "comments": PartThreadManager(
                    part, thread_attr="documents_thread"
                ).comments(),
            },
        }
