"""Struct: aggregated read model for one AssetReservation — the row plus its
typed change log (ReservationUpdate)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.dispatching.models.reservations.reservation_update import ReservationUpdate


@dataclass
class ReservationStruct:
    reservation: AssetReservation
    updates: list[ReservationUpdate] = field(default_factory=list)

    @classmethod
    def load(cls, *, reservation_id: int) -> "ReservationStruct":
        reservation = AssetReservation.objects.select_related(
            "asset", "dispatch", "accountable_person", "domain"
        ).get(pk=reservation_id, deleted_at__isnull=True)
        updates = list(
            reservation.updates.select_related("actor").order_by("-created_at")
        )
        return cls(reservation=reservation, updates=updates)

    @property
    def reservation_id(self) -> int:
        return self.reservation.pk

    def to_dict(self) -> dict:
        return {
            "id": self.reservation_id,
            "asset_id": self.reservation.asset_id,
            "dispatch_id": self.reservation.dispatch_id,
            "reservation_status": self.reservation.reservation_status,
            "reservation_type": self.reservation.reservation_type,
            "scheduled_start": self.reservation.scheduled_start,
            "scheduled_end": self.reservation.scheduled_end,
            "accountable_person_id": self.reservation.accountable_person_id,
            "update_count": len(self.updates),
        }
