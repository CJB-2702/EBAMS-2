"""Guard type: Policy. Deletion is legal only before any handover, on either
track — after that the booking is history and must be cancelled, never
deleted (dispatching_starter_kit/3_asset_reservations.md §9, R12)."""

from __future__ import annotations


class ReservationDeletionPolicy:
    @classmethod
    def check(cls, *, reservation) -> None:
        handed_over = bool(
            reservation.physical_checkout_at
            or reservation.user_checkout_submitted_at
        )
        if handed_over:
            raise ValueError(
                "Cannot delete a reservation after any handover has occurred — "
                "cancel it instead."
            )
