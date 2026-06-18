"""MeterManager — meter readings sub-area of AssetContext.

Writes one MeterHistory row per changed meter index and refreshes the cached
``Asset.meter1..4`` columns, in one transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.assets.models import MeterHistory

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset

_METER_FIELDS = {1: "meter1", 2: "meter2", 3: "meter3", 4: "meter4"}


class MeterManager:
    def __init__(self, asset: "Asset", actor: "AbstractUser") -> None:
        self.asset = asset
        self.actor = actor

    def record(
        self,
        readings: dict[int, float],
        *,
        recorded_at=None,
        source: str | None = None,
    ) -> list[MeterHistory]:
        """``readings`` maps meter index (1-4) → value. Writes only changes."""
        valid = {i: v for i, v in readings.items() if i in _METER_FIELDS and v is not None}
        if not valid:
            raise ValueError("At least one valid meter reading (index 1-4) is required.")

        when = recorded_at or timezone.now()
        created: list[MeterHistory] = []
        with transaction.atomic():
            changed_fields: list[str] = []
            for index, value in valid.items():
                field = _METER_FIELDS[index]
                if getattr(self.asset, field) == value:
                    continue
                created.append(
                    MeterHistory.objects.create(
                        asset=self.asset,
                        meter_index=index,
                        value=value,
                        recorded_at=when,
                        source=source,
                        created_by=self.actor,
                        updated_by=self.actor,
                    )
                )
                setattr(self.asset, field, value)
                changed_fields.append(field)

            if changed_fields:
                self.asset.updated_by = self.actor
                self.asset.save(update_fields=[*changed_fields, "updated_by", "updated_at"])
        return created
