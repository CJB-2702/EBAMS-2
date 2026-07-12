"""PartDefinitionStruct — the super-struct: a full Part view from the id alone.

Composes ``PartStruct`` + ``PartRevisionHistoryStruct`` + ``PartSourcingStruct``
eagerly (row lists only — per-row threads stay lazy) and exposes ``.aliases()``
and ``.domains()`` as lazy methods that query on first call rather than always
loading (struct plan §3). Built for ``part_detail`` and any future full-part
view (export, admin JSON); slice callers that need one deep slice should use the
slice struct directly with ``eager_thread=True`` instead.
"""

from __future__ import annotations

from app.parts.control_layer.domain_structs.part_structs.part_alias_index_struct import (
    PartAliasIndexStruct,
)
from app.parts.control_layer.domain_structs.part_structs.part_revision_history_struct import (
    PartRevisionHistoryStruct,
)
from app.parts.control_layer.domain_structs.part_structs.part_sourcing_struct import (
    PartSourcingStruct,
)
from app.parts.control_layer.domain_structs.part_structs.part_struct import PartStruct
from app.parts.models import PartDomainAccessMapping


class PartDefinitionStruct:
    def __init__(self, part_id: int) -> None:
        self.part_id = part_id
        # Raises PartNotFoundError if the Part does not exist — the existence
        # guarantee for the whole aggregate.
        self.part_struct = PartStruct(part_id)
        # Row lists eager, per-row threads lazy (thread=False).
        self.revision_history = PartRevisionHistoryStruct.from_id(part_id)
        self.sourcing = PartSourcingStruct.from_id(part_id)

    @classmethod
    def from_id(cls, part_id: int) -> "PartDefinitionStruct":
        return cls(part_id)

    # -- lazy slices: queried on first call, not loaded up front -------------- #

    def aliases(self) -> list[dict]:
        return PartAliasIndexStruct.from_id(self.part_id).to_dict()

    def domains(self) -> list[dict]:
        mappings = (
            PartDomainAccessMapping.objects.filter(part_id=self.part_id, is_active=True)
            .select_related("domain")
            .order_by("domain__name")
        )
        return [
            {"id": m.domain_id, "name": m.domain.name, "slug": m.domain.slug}
            for m in mappings
        ]

    def to_dict(self) -> dict:
        data = self.part_struct.to_dict()
        data["revisions"] = self.revision_history.to_dict()
        data["supplier_items"] = self.sourcing.supplier_items()
        data["manufacturers"] = self.sourcing.manufacturers()
        return data
