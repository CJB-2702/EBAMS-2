"""Guard type: StateMachine. Legal reservation_status transitions
(dispatching_starter_kit/3_asset_reservations.md §9).

Tentative -> Confirmed -> {UserCheckedOut | CheckedOut} -> {UserReturned |
Returned}, plus Cancelled (from any non-terminal state) and NoShow (from
Confirmed only).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.dispatching.models.enums import ReservationStatus

RESERVATION_STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    ReservationStatus.TENTATIVE: frozenset(
        {ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED}
    ),
    ReservationStatus.CONFIRMED: frozenset(
        {
            ReservationStatus.USER_CHECKED_OUT,
            ReservationStatus.CHECKED_OUT,
            ReservationStatus.CANCELLED,
            ReservationStatus.NO_SHOW,
        }
    ),
    ReservationStatus.USER_CHECKED_OUT: frozenset(
        {ReservationStatus.CHECKED_OUT, ReservationStatus.USER_RETURNED, ReservationStatus.CANCELLED}
    ),
    ReservationStatus.CHECKED_OUT: frozenset(
        {ReservationStatus.USER_RETURNED, ReservationStatus.RETURNED}
    ),
    ReservationStatus.USER_RETURNED: frozenset({ReservationStatus.CHECKED_OUT, ReservationStatus.RETURNED}),
    ReservationStatus.RETURNED: frozenset(),
    ReservationStatus.CANCELLED: frozenset(),
    ReservationStatus.NO_SHOW: frozenset(),
}


@dataclass(frozen=True)
class TransitionVerdict:
    allowed: bool
    reason: str = ""


class ReservationTransitionStateMachine:
    """StateMachine: is this reservation_status transition legal?"""

    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> TransitionVerdict:
        if from_status == to_status:
            return TransitionVerdict(allowed=False, reason="Already in that state.")
        legal = RESERVATION_STATE_TRANSITIONS.get(from_status)
        if legal is None:
            return TransitionVerdict(
                allowed=False, reason=f"'{from_status}' is not a known reservation status."
            )
        if to_status not in legal:
            return TransitionVerdict(
                allowed=False,
                reason=f"Cannot move from '{from_status}' to '{to_status}'.",
            )
        return TransitionVerdict(allowed=True)
