"""Struct: row and aggregate read models over `ActiveInventory`."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from app.inventory.models.stock.active_inventory import ActiveInventory


@dataclass(frozen=True)
class ActiveInventoryRowStruct:
    balance_id: int
    warehouse_id: int
    warehouse_code: str
    room_id: int
    room_name: str
    storage_location_id: int | None
    display_code: str
    part_id: int
    part_number: str
    part_name: str
    serial_number: str
    quantity_on_hand: Decimal
    quantity_allocated: Decimal
    unit_cost_avg: Decimal | None
    is_unassigned: bool
    last_audited_at: object

    @property
    def quantity_available(self) -> Decimal:
        return self.quantity_on_hand - self.quantity_allocated

    @classmethod
    def from_model(cls, balance: ActiveInventory) -> "ActiveInventoryRowStruct":
        return cls(
            balance_id=balance.pk,
            warehouse_id=balance.warehouse_id,
            warehouse_code=balance.warehouse.code,
            room_id=balance.room_id,
            room_name=balance.room.room_name,
            storage_location_id=balance.storage_location_id,
            display_code=(
                balance.storage_location.display_code
                if balance.storage_location_id
                else ""
            ),
            part_id=balance.part_id,
            part_number=balance.part.part_number,
            part_name=balance.part.name,
            serial_number=balance.serial_number,
            quantity_on_hand=balance.quantity_on_hand,
            quantity_allocated=balance.quantity_allocated,
            unit_cost_avg=balance.unit_cost_avg,
            is_unassigned=balance.is_unassigned,
            last_audited_at=balance.last_audited_at,
        )

    def to_dict(self) -> dict:
        return {
            "balance_id": self.balance_id,
            "warehouse_id": self.warehouse_id,
            "warehouse_code": self.warehouse_code,
            "room_id": self.room_id,
            "room_name": self.room_name,
            "storage_location_id": self.storage_location_id,
            "display_code": self.display_code,
            "part_id": self.part_id,
            "part_number": self.part_number,
            "part_name": self.part_name,
            "serial_number": self.serial_number,
            "quantity_on_hand": self.quantity_on_hand,
            "quantity_allocated": self.quantity_allocated,
            "quantity_available": self.quantity_available,
            "unit_cost_avg": self.unit_cost_avg,
            "is_unassigned": self.is_unassigned,
            "last_audited_at": self.last_audited_at,
        }


@dataclass(frozen=True)
class PartStockAggregateStruct:
    """One part's stock totals across every room a caller can see."""

    part_id: int
    part_number: str
    total_on_hand: Decimal
    total_allocated: Decimal
    room_count: int

    @classmethod
    def load(cls, *, part_id: int, room_ids=None) -> "PartStockAggregateStruct":
        qs = ActiveInventory.objects.filter(part_id=part_id)
        if room_ids is not None:
            qs = qs.filter(room_id__in=room_ids)
        agg = qs.aggregate(
            total_on_hand=Sum("quantity_on_hand"),
            total_allocated=Sum("quantity_allocated"),
        )
        room_count = qs.values("room_id").distinct().count()
        part = qs.values("part__part_number").first()
        return cls(
            part_id=part_id,
            part_number=part["part__part_number"] if part else "",
            total_on_hand=agg["total_on_hand"] or Decimal("0"),
            total_allocated=agg["total_allocated"] or Decimal("0"),
            room_count=room_count,
        )


@dataclass(frozen=True)
class RoomStockAggregateStruct:
    """One room's stock totals — distinct part/serial line count and on-hand
    total, used by room-level summaries."""

    room_id: int
    total_on_hand: Decimal
    balance_row_count: int

    @classmethod
    def load(cls, *, room_id: int) -> "RoomStockAggregateStruct":
        qs = ActiveInventory.objects.filter(room_id=room_id)
        agg = qs.aggregate(total_on_hand=Sum("quantity_on_hand"))
        return cls(
            room_id=room_id,
            total_on_hand=agg["total_on_hand"] or Decimal("0"),
            balance_row_count=qs.count(),
        )
