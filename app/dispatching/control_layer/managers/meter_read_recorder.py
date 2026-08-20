"""Manager: writes the dispatcher's meter readings through the assets-owned
path (AssetContext.meters) and stores the resulting MeterHistory row back onto
the reservation's initial_meter_read / final_meter_read reference.

**Only the dispatcher track reaches here.** The user-reported numbers live on
the reservation itself (AssetReservation.user_meterN_out/in) and are reference
information — they never become an asset reading. A dispatcher recording a
meter, by contrast, *is* an official meter update: it writes MeterHistory and
moves Asset.meterN, exactly as if it had been entered on the asset itself
(dispatching_starter_kit/3_asset_reservations.md §7.3).

Several meters may be recorded in one handover. MeterHistory is the authority
for the full set; the reservation's two FKs point at the lowest-indexed reading
of each batch, which is the one a summary line wants to show.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import MeterHistory
    from app.dispatching.models.reservations.asset_reservation import AssetReservation


class MeterReadRecorder:
    @classmethod
    def _record(
        cls,
        *,
        reservation: "AssetReservation",
        readings: dict[int, float],
        actor: "AbstractUser",
        recorded_at=None,
        source: str,
    ) -> list["MeterHistory"]:
        from app.assets.control_layer.asset_context import AssetContext

        clean = {i: v for i, v in (readings or {}).items() if v is not None}
        if not clean:
            return []
        # MeterManager writes only *changes*, so re-recording a value the asset
        # already holds legitimately returns nothing. That is not an error, and
        # the reservation's FK simply stays as it was.
        return AssetContext(reservation.asset_id, actor).meters.record(
            clean, recorded_at=recorded_at, source=source
        )

    @classmethod
    def _attach(
        cls,
        *,
        reservation: "AssetReservation",
        created: list["MeterHistory"],
        field_name: str,
        actor: "AbstractUser",
    ) -> "MeterHistory | None":
        if not created:
            return None
        primary = min(created, key=lambda row: row.meter_index)
        setattr(reservation, field_name, primary)
        reservation.updated_by = actor
        reservation.save(update_fields=[field_name, "updated_by", "updated_at"])
        return primary

    @classmethod
    def record_initial(
        cls, *, reservation: "AssetReservation", readings: dict[int, float],
        actor: "AbstractUser", recorded_at=None,
    ) -> list["MeterHistory"]:
        created = cls._record(
            reservation=reservation, readings=readings, actor=actor,
            recorded_at=recorded_at, source="dispatching_checkout",
        )
        cls._attach(
            reservation=reservation, created=created,
            field_name="initial_meter_read", actor=actor,
        )
        return created

    @classmethod
    def record_final(
        cls, *, reservation: "AssetReservation", readings: dict[int, float],
        actor: "AbstractUser", recorded_at=None,
    ) -> list["MeterHistory"]:
        created = cls._record(
            reservation=reservation, readings=readings, actor=actor,
            recorded_at=recorded_at, source="dispatching_return",
        )
        cls._attach(
            reservation=reservation, created=created,
            field_name="final_meter_read", actor=actor,
        )
        return created
