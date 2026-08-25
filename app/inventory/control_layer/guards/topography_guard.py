"""Guard types: Validator + Policy.

The validators are input and uniqueness pre-checks for warehouses and
storage locations, so a bad coordinate or duplicate code surfaces as a
friendly `InventoryValidationError` instead of an `IntegrityError`.

The policies are the stock-protection rules ported from the legacy storeroom
designer and tightened: a bin holding stock cannot be retired, an XY location
with stock underneath it cannot be retired, and a replacement layout SVG that
would orphan a stock-holding location is rejected outright rather than
silently accepted.
"""

from __future__ import annotations

from app.inventory.control_layer.errors import InventoryValidationError
from app.inventory.models.stock.active_inventory import ActiveInventory
from app.inventory.models.topography.room import Room
from app.inventory.models.topography.room_location import RoomLocation
from app.inventory.models.topography.storage_location import StorageLocation
from app.inventory.models.topography.warehouse import Warehouse


class WarehouseValidator:
    @classmethod
    def check_code_unique(cls, *, code: str, exclude_id: int | None = None) -> None:
        qs = Warehouse.objects.filter(code=code)
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"Warehouse code '{code}' is already in use."]
            )


class RoomValidator:
    @classmethod
    def check_name_non_empty(cls, *, room_name: str) -> None:
        if not (room_name or "").strip():
            raise InventoryValidationError(["Room name cannot be blank."])

    @classmethod
    def check_name_unique(
        cls, *, warehouse_id: int, room_name: str, exclude_id: int | None = None
    ) -> None:
        qs = Room.objects.filter(warehouse_id=warehouse_id, room_name=room_name)
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"A room named '{room_name}' already exists in this warehouse."]
            )


class RoomLocationValidator:
    @classmethod
    def check_coordinates_non_empty(cls, *, major_coord: str, minor_coord: str) -> None:
        errors = []
        for label, value in (("Major", major_coord), ("Minor", minor_coord)):
            if not (value or "").strip():
                errors.append(f"{label} coordinate cannot be blank.")
        if errors:
            raise InventoryValidationError(errors)

    @classmethod
    def check_unique(
        cls,
        *,
        room_id: int,
        major_coord: str,
        minor_coord: str,
        exclude_id: int | None = None,
    ) -> None:
        qs = RoomLocation.objects.filter(
            room_id=room_id, major_coord=major_coord, minor_coord=minor_coord
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"{major_coord}-{minor_coord} already exists in this room."]
            )


class StorageLocationValidator:
    @classmethod
    def check_atomic_coord_non_empty(cls, *, atomic_coord: str) -> None:
        if not (atomic_coord or "").strip():
            raise InventoryValidationError(["Atomic coordinate cannot be blank."])

    @classmethod
    def check_unique(
        cls,
        *,
        room_location_id: int,
        atomic_coord: str,
        exclude_id: int | None = None,
    ) -> None:
        qs = StorageLocation.objects.filter(
            room_location_id=room_location_id, atomic_coord=atomic_coord
        )
        if exclude_id is not None:
            qs = qs.exclude(pk=exclude_id)
        if qs.exists():
            raise InventoryValidationError(
                [f"Atomic coordinate '{atomic_coord}' already exists at this location."]
            )


class StorageLocationPolicy:
    """Guard type: Policy. Stock presence is what makes a bin undeletable.

    A `StorageLocation` carrying any `ActiveInventory` row cannot be
    deactivated — the row is a live pointer at that bin, and
    `StockLedgerManager.withdraw` deletes balances the moment they reach
    zero, so "a row exists" already means "stock lives here". Move or issue
    the stock first, then retire the bin.
    """

    @classmethod
    def check_deactivate(cls, *, storage_location) -> None:
        count = ActiveInventory.objects.filter(
            storage_location=storage_location
        ).count()
        if count:
            raise InventoryValidationError(
                [
                    f"'{storage_location.display_code}' still holds {count} stock "
                    f"row{'' if count == 1 else 's'} and cannot be retired. Move or "
                    f"issue the stock first."
                ]
            )


class RoomLocationPolicy:
    """Guard type: Policy. An XY location is undeletable while any bin under
    it still holds stock — the same rule as `StorageLocationPolicy`, lifted
    one tier so a user cannot retire the parent to sidestep the child check.
    """

    @classmethod
    def check_deactivate(cls, *, room_location) -> None:
        blocked = list(
            ActiveInventory.objects.filter(
                storage_location__room_location=room_location
            )
            .values_list("storage_location__display_code", flat=True)
            .distinct()
        )
        if blocked:
            raise InventoryValidationError(
                [
                    f"'{room_location.display_code}' cannot be retired — stock is "
                    f"still held at: {', '.join(sorted(blocked))}."
                ]
            )


class LayoutReconciliationPolicy:
    """Guard type: Policy. A replacement layout may not orphan stock.

    An uploaded SVG that has no shape for an existing location leaves that
    location "orphaned" — still in the database, but no longer reachable
    from the map. That is tolerable for an empty location and unacceptable
    for one holding stock, which would become invisible to every operator
    working from the picture. **The default is to reject the whole upload**;
    nothing is archived and no `current_layout` is replaced.

    `allow_orphaned_stock=True` is the deliberate override seam. No UI path
    passes it today — it exists so a future "acknowledge and proceed" flow
    has somewhere to plug in rather than deleting this check.
    """

    @classmethod
    def _fail(cls, *, tier: str, blocked: list[str]) -> None:
        raise InventoryValidationError(
            [
                f"Upload rejected: the new layout has no shape for {len(blocked)} "
                f"{tier} that still hold{'s' if len(blocked) == 1 else ''} stock "
                f"({', '.join(sorted(blocked))}). Move the stock, or add matching "
                f"shapes to the SVG, then upload again."
            ]
        )

    @classmethod
    def check_room_orphans(
        cls, *, room, orphaned_codes, allow_orphaned_stock: bool = False
    ) -> None:
        if allow_orphaned_stock or not orphaned_codes:
            return
        blocked = list(
            RoomLocation.objects.filter(
                room=room,
                display_code__in=list(orphaned_codes),
                storage_locations__stock__isnull=False,
            )
            .values_list("display_code", flat=True)
            .distinct()
        )
        if blocked:
            cls._fail(tier="location(s)", blocked=blocked)

    @classmethod
    def check_room_location_orphans(
        cls, *, room_location, orphaned_codes, allow_orphaned_stock: bool = False
    ) -> None:
        if allow_orphaned_stock or not orphaned_codes:
            return
        blocked = list(
            StorageLocation.objects.filter(
                room_location=room_location,
                atomic_coord__in=list(orphaned_codes),
                stock__isnull=False,
            )
            .values_list("atomic_coord", flat=True)
            .distinct()
        )
        if blocked:
            cls._fail(tier="bin(s)", blocked=blocked)
