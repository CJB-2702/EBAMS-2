"""Search: the movements ledger list (`/inventory/movements`)."""

from __future__ import annotations

from django.db.models import Q, QuerySet

from app.inventory.models.movements.part_movement import PartMovement
from app.inventory.presentation_layer.search.active_inventory_search import (
    domain_visible_room_ids,
)


class MovementSearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        movement_type: str = "",
        part_q: str = "",
        warehouse_id: str = "",
    ) -> QuerySet[PartMovement]:
        visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
        qs = PartMovement.objects.filter(
            Q(from_room_id__in=visible_room_ids) | Q(to_room_id__in=visible_room_ids)
        ).select_related(
            "part", "from_warehouse", "from_room", "from_storage_location",
            "to_warehouse", "to_room", "to_storage_location", "moved_by",
        )

        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        if part_q:
            qs = qs.filter(
                Q(part__part_number__icontains=part_q) | Q(part__name__icontains=part_q)
            )
        if warehouse_id:
            qs = qs.filter(
                Q(from_warehouse_id=warehouse_id) | Q(to_warehouse_id=warehouse_id)
            )

        return qs.order_by("-movement_date")
