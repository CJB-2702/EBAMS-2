"""Manager: the ONLY writer to `ActiveInventory` (FD-11, FD-12). Intake,
movements, issuance, and audits (Phases 4/6/6/7) all mutate stock through
this seam — never `ActiveInventory.objects.create/update/delete` directly.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.inventory.control_layer.errors import InsufficientStockError
from app.inventory.control_layer.guards.stock_guard import StockPolicy, StockValidator
from app.inventory.models.stock.active_inventory import ActiveInventory


class StockLedgerManager:
    @classmethod
    def inject(
        cls,
        *,
        warehouse,
        room,
        storage_location,
        part,
        qty: Decimal,
        serial: str = "",
        unit_cost: Decimal | None = None,
        actor=None,
    ) -> ActiveInventory:
        """Add quantity to (or create) a balance row.

        Non-serialized rows are aggregated by `get_or_create` inside
        `select_for_update`, so two injects into the same NULL-location
        Intake-Room balance yield one row rather than a duplicate the
        nullable-FK unique constraint can't catch on its own (FD-12).
        Serialized rows are always a fresh unit row — a repeated serial is a
        hard `SerialInUseError`, never an aggregate.
        """
        StockValidator.check_quantity_positive(qty=qty)
        StockValidator.check_serial_implies_unit_qty(serial=serial, qty=qty)
        StockPolicy.check_domain_access(actor=actor, room=room)

        with transaction.atomic():
            if serial:
                StockValidator.check_serial_available(part_id=part.pk, serial=serial)
                return ActiveInventory.objects.create(
                    warehouse=warehouse,
                    room=room,
                    storage_location=storage_location,
                    part=part,
                    serial_number=serial,
                    quantity_on_hand=qty,
                    unit_cost_avg=unit_cost,
                    is_unassigned=room.is_intake_room and storage_location is None,
                    created_by=actor,
                    updated_by=actor,
                )

            locked_qs = ActiveInventory.objects.select_for_update().filter(
                room=room,
                storage_location=storage_location,
                part=part,
                serial_number="",
            )
            balance = locked_qs.first()
            if balance is None:
                return ActiveInventory.objects.create(
                    warehouse=warehouse,
                    room=room,
                    storage_location=storage_location,
                    part=part,
                    serial_number="",
                    quantity_on_hand=qty,
                    unit_cost_avg=unit_cost,
                    is_unassigned=room.is_intake_room and storage_location is None,
                    created_by=actor,
                    updated_by=actor,
                )

            new_qty = balance.quantity_on_hand + qty
            balance.unit_cost_avg = cls._weighted_average_cost(
                existing_qty=balance.quantity_on_hand,
                existing_cost=balance.unit_cost_avg,
                added_qty=qty,
                added_cost=unit_cost,
            )
            balance.quantity_on_hand = new_qty
            balance.updated_by = actor
            balance.save(
                update_fields=[
                    "quantity_on_hand",
                    "unit_cost_avg",
                    "updated_by",
                    "updated_at",
                ]
            )
            return balance

    @classmethod
    def withdraw(
        cls,
        *,
        room,
        storage_location,
        part,
        qty: Decimal,
        serial: str = "",
        actor=None,
    ) -> ActiveInventory | None:
        """Decrement a balance; deletes serialized unit rows at zero.
        Raises `InsufficientStockError` before any write."""
        StockValidator.check_quantity_positive(qty=qty)
        StockPolicy.check_domain_access(actor=actor, room=room)

        with transaction.atomic():
            balance = (
                ActiveInventory.objects.select_for_update()
                .filter(
                    room=room,
                    storage_location=storage_location,
                    part=part,
                    serial_number=serial,
                )
                .first()
            )
            available = balance.quantity_on_hand if balance else Decimal("0")
            if balance is None or available < qty:
                raise InsufficientStockError(
                    part_id=part.pk, requested=qty, available=available
                )

            remaining = balance.quantity_on_hand - qty
            if serial or remaining == 0:
                balance.delete()
                return None

            balance.quantity_on_hand = remaining
            balance.updated_by = actor
            balance.save(update_fields=["quantity_on_hand", "updated_by", "updated_at"])
            return balance

    @classmethod
    def transfer(
        cls,
        *,
        warehouse,
        from_room,
        from_storage_location,
        to_room,
        to_storage_location,
        part,
        qty: Decimal,
        serial: str = "",
        actor=None,
    ) -> ActiveInventory:
        """Withdraw+inject in one transaction — Phase 6's movement primitive."""
        with transaction.atomic():
            withdrawn = (
                ActiveInventory.objects.filter(
                    room=from_room,
                    storage_location=from_storage_location,
                    part=part,
                    serial_number=serial,
                )
                .values("unit_cost_avg")
                .first()
            )
            unit_cost = withdrawn["unit_cost_avg"] if withdrawn else None

            cls.withdraw(
                room=from_room,
                storage_location=from_storage_location,
                part=part,
                qty=qty,
                serial=serial,
                actor=actor,
            )
            return cls.inject(
                warehouse=warehouse,
                room=to_room,
                storage_location=to_storage_location,
                part=part,
                qty=qty,
                serial=serial,
                unit_cost=unit_cost,
                actor=actor,
            )

    @staticmethod
    def _weighted_average_cost(
        *,
        existing_qty: Decimal,
        existing_cost: Decimal | None,
        added_qty: Decimal,
        added_cost: Decimal | None,
    ) -> Decimal | None:
        if added_cost is None:
            return existing_cost
        if existing_cost is None or existing_qty == 0:
            return added_cost
        total_qty = existing_qty + added_qty
        if total_qty == 0:
            return existing_cost
        weighted = (
            (existing_qty * existing_cost) + (added_qty * added_cost)
        ) / total_qty
        return weighted.quantize(existing_cost)
