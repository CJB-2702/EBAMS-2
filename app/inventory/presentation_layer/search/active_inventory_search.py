"""Search: the browsable stock list. Domain-scoped — rooms whose effective
domains the requesting user's domain_ids do not intersect are excluded
before the main filter runs, mirroring `RoomDomainPolicy.effective_domains`
without importing the control-layer guard's per-request `user_covers_room`
(that needs a live user; this needs a room_id set for a queryset filter).
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import F, Q, QuerySet
from django.utils import timezone

from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room


def domain_visible_room_ids(*, domain_ids) -> list[int]:
    """Rooms with no warehouse domains at all are open to everyone (mirrors
    Part.is_domain_limited's default-open convention); otherwise the room is
    visible when at least one of its effective domains (warehouse domains
    minus room-level exclusions) is in domain_ids. Computed in Python over
    the room table (small at dev/prod scale) since the set-difference is
    awkward to express per-row in SQL."""
    domain_id_set = set(domain_ids)
    visible_ids = []
    for room in Room.objects.all().prefetch_related(
        "warehouse__domains", "excluded_domains"
    ):
        warehouse_domain_ids = {d.id for d in room.warehouse.domains.all()}
        if not warehouse_domain_ids:
            visible_ids.append(room.id)
            continue
        effective = warehouse_domain_ids - {d.id for d in room.excluded_domains.all()}
        if effective & domain_id_set:
            visible_ids.append(room.id)
    return visible_ids


class ActiveInventorySearch:
    @classmethod
    def index_list(
        cls,
        *,
        domain_ids,
        warehouse_id: str = "",
        room_id: str = "",
        storage_location_id: str = "",
        room_location_code: str = "",
        part_q: str = "",
        part_id: int | None = None,
        part_number: str = "",
        part_name: str = "",
        generic_q: str = "",
        serial: str = "",
        stock_status: str = "",
        low_stock_only: bool = False,
        out_of_stock_only: bool = False,
        has_stock_only: bool = False,
        unassigned_only: bool = False,
        stale_days: int | None = None,
    ) -> QuerySet[ActiveInventory]:
        visible_room_ids = domain_visible_room_ids(domain_ids=domain_ids)
        qs = (
            ActiveInventory.objects.filter(room_id__in=visible_room_ids)
            .select_related("warehouse", "room", "storage_location", "part")
            .annotate(quantity_available=F("quantity_on_hand") - F("quantity_allocated"))
        )

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)
        if room_id:
            qs = qs.filter(room_id=room_id)
        if storage_location_id:
            qs = qs.filter(storage_location_id=storage_location_id)
        # Map Area (XY) filter — the FK-backed equivalent of "storage code
        # starts with this area code", without a string LIKE.
        if room_location_code:
            qs = qs.filter(
                storage_location__room_location__display_code=room_location_code
            )
        # Locked-part callers (the issuance bin search) pin the list to one
        # part rather than text-matching it — the clerk must not be able to
        # widen a demand's picker onto a different part.
        if part_id:
            qs = qs.filter(part_id=part_id)
        if part_q:
            qs = qs.filter(
                Q(part__part_number__icontains=part_q) | Q(part__name__icontains=part_q)
            )
        if part_number:
            qs = qs.filter(part__part_number__icontains=part_number)
        if part_name:
            qs = qs.filter(part__name__icontains=part_name)
        if serial:
            qs = qs.filter(serial_number__icontains=serial)
        # The issuance workspace's one-box search: someone reading a label off
        # a shelf has a part number OR a serial and should not have to know
        # which box it belongs in.
        if generic_q:
            qs = qs.filter(
                Q(part__part_number__icontains=generic_q)
                | Q(part__name__icontains=generic_q)
                | Q(serial_number__icontains=generic_q)
            )

        # Stock status filters
        if stock_status == "has_stock" or has_stock_only:
            qs = qs.filter(quantity_on_hand__gt=0)
        elif stock_status == "low_stock" or low_stock_only:
            qs = qs.filter(quantity_on_hand__gt=0, quantity_on_hand__lte=10)
        elif stock_status == "out_of_stock" or out_of_stock_only:
            qs = qs.filter(quantity_on_hand__lte=0)

        if unassigned_only:
            qs = qs.filter(is_unassigned=True)
        if stale_days is not None:
            cutoff = timezone.now() - timedelta(days=stale_days)
            qs = qs.filter(
                Q(last_audited_at__isnull=True) | Q(last_audited_at__lt=cutoff)
            )

        return qs.order_by("warehouse", "room", "storage_location", "part")

