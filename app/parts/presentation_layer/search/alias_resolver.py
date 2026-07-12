"""AliasResolver — value -> Part, the heart of search (D9). Read-only;
collapses every alias kind to a Part via the primary `part` anchor directly
(no forward hop through supplier_item)."""

from __future__ import annotations

from app.parts.control_layer.domain_structs.part_structs.part_struct import PartStruct
from app.parts.models import Alias


def _normalize(value: str) -> str:
    return (value or "").strip().casefold()


class AliasResolver:
    @staticmethod
    def resolve(value: str) -> list[PartStruct]:
        normalized = _normalize(value)
        if not normalized:
            return []

        exact = Alias.objects.filter(normalized_value=normalized).select_related("part")
        hits = list(exact)
        if not hits:
            hits = list(
                Alias.objects.filter(
                    normalized_value__startswith=normalized
                ).select_related("part")[:25]
            )

        seen_part_ids: set[int] = set()
        structs: list[PartStruct] = []
        for alias in hits:
            if alias.part_id in seen_part_ids:
                continue
            seen_part_ids.add(alias.part_id)
            structs.append(PartStruct.from_instance(alias.part))
        return structs
