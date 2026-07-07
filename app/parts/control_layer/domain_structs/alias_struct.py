from __future__ import annotations

from app.parts.models import Alias


class AliasStruct:
    def __init__(self, alias: Alias) -> None:
        self.alias = alias

    def to_dict(self) -> dict:
        a = self.alias
        return {
            "alias": a.alias,
            "alias_type": a.alias_type,
            "association_type": a.association_type,
            "source": a.source,
            "resolved_part": {
                "id": a.part_id,
                "part_number": a.part.part_number,
                "name": a.part.name,
            },
        }
