"""PartAliasIndexStruct — all Alias rows anchored to a Part (D9's "this Part's
aliases" rule). Net-new: no struct loaded a part's full alias list before, so it
also backs a future "known aliases / MPNs" panel on the Part detail page.
``eager_supplier_items`` prefetches the optional vendor-item secondary link.
"""

from __future__ import annotations

from app.parts.models import Alias


class PartAliasIndexStruct:
    def __init__(self, part_id: int, *, eager_supplier_items: bool = False) -> None:
        self.part_id = part_id
        qs = Alias.objects.filter(part_id=part_id)
        if eager_supplier_items:
            qs = qs.select_related("supplier_item")
        self.aliases: list[Alias] = list(qs.order_by("normalized_value"))

    @classmethod
    def from_id(cls, part_id: int, *, eager_supplier_items: bool = False) -> "PartAliasIndexStruct":
        return cls(part_id, eager_supplier_items=eager_supplier_items)

    def to_dict(self) -> list[dict]:
        return [
            {
                "id": a.id,
                "alias": a.alias,
                "alias_type": a.alias_type,
                "association_type": a.association_type,
                "source": a.source,
                "supplier_item_id": a.supplier_item_id,
                "alternate_part_id": a.alternate_part_id,
            }
            for a in self.aliases
        ]
