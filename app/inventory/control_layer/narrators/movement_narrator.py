"""Narrator: `PartMovement` numbering plus human-readable audit text.

Numbering lives here rather than a factory (mirrors `IntakeNarrator`'s home
for this app's control-layer text) — `MOV-YYYY-#####`, sequential per
calendar year (part_movements.md deliverables).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.inventory.models.movements.part_movement import PartMovement


class MovementNarrator:
    @classmethod
    def generate_movement_number(cls) -> str:
        year = timezone.now().year
        prefix = f"MOV-{year}-"
        with transaction.atomic():
            last = (
                PartMovement.objects.select_for_update()
                .filter(movement_number__startswith=prefix)
                .order_by("-movement_number")
                .first()
            )
            next_seq = int(last.movement_number[-5:]) + 1 if last else 1
        return f"{prefix}{next_seq:05d}"

    @staticmethod
    def movement_logged(
        *,
        movement_type: str,
        part_number: str,
        quantity: Decimal,
        from_path: str,
        to_path: str,
        serial_number: str = "",
    ) -> str:
        serial = f" SN:{serial_number}" if serial_number else ""
        return (
            f"{movement_type}: {quantity} x {part_number}{serial} moved "
            f"{from_path} -> {to_path}."
        )
