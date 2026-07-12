"""PartSearch — the seam Phase 4's lookup page calls. Wraps AliasResolver plus
direct part_number/name matching. Provisional minimal ranking (OQ7): exact
alias > prefix alias > name contains."""

from __future__ import annotations

from app.parts.control_layer.domain_structs.part_structs.part_struct import PartStruct
from app.parts.models import Part
from app.parts.presentation_layer.search.alias_resolver import AliasResolver


class PartSearch:
    @staticmethod
    def query(term: str) -> list[PartStruct]:
        term = (term or "").strip()
        if not term:
            return []

        alias_hits = AliasResolver.resolve(term)
        seen_part_ids = {s.part_id for s in alias_hits}

        direct = Part.objects.filter(name__icontains=term).exclude(
            id__in=seen_part_ids
        )[:25]
        direct_structs = [PartStruct.from_instance(p) for p in direct]

        return alias_hits + direct_structs
