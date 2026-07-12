"""PartStruct — aggregated read model for a single Part. Proves D3: a full view
is reachable from the base Part id alone."""

from __future__ import annotations

from app.parts.models import Part, PartRevision


class PartNotFoundError(Exception):
    pass


class PartStruct:
    def __init__(self, part_id: int, *, eager: bool = False) -> None:
        self.part_id = part_id
        qs = Part.objects.all()
        if eager:
            qs = qs.prefetch_related("revisions")
        try:
            self.part: Part = qs.get(id=part_id)
        except Part.DoesNotExist as exc:
            raise PartNotFoundError(f"Part {part_id} not found.") from exc

        self.current_revision: PartRevision | None = (
            PartRevision.objects.filter(part_id=part_id)
            .order_by("-major_revision_number", "-minor_revision_number")
            .first()
        )
        self.revision_count: int = PartRevision.objects.filter(part_id=part_id).count()

    @classmethod
    def from_instance(cls, part: Part) -> "PartStruct":
        struct = cls.__new__(cls)
        struct.part_id = part.id
        struct.part = part
        struct.current_revision = (
            PartRevision.objects.filter(part_id=part.id)
            .order_by("-major_revision_number", "-minor_revision_number")
            .first()
        )
        struct.revision_count = PartRevision.objects.filter(part_id=part.id).count()
        return struct

    def to_dict(self) -> dict:
        p = self.part
        rev = self.current_revision
        return {
            "id": p.id,
            "part_number": p.part_number,
            "name": p.name,
            "description": p.description,
            "part_type": p.part_type,
            "category": p.category,
            "is_active": p.is_active,
            "is_domain_limited": p.is_domain_limited,
            "current_revision": (
                {
                    "id": rev.id,
                    "major": rev.major_revision_number,
                    "minor": rev.minor_revision_number,
                    "major_name": rev.major_revision_name,
                    "minor_name": rev.minor_revision_name,
                    "status": rev.status,
                    "date_of_release": rev.date_of_release,
                }
                if rev is not None
                else None
            ),
            "revision_count": self.revision_count,
        }
