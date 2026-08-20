"""Narrator: machine-written activity-log sentences for a reservation.

Kept separate from ReservationContext so wording changes in one place and is
testable without opening a reservation. See doc 4 §5.2: automatic, plain
language, distinguishable from human comments, never the audit trail —
reporting reads ReservationUpdate, not this text.
"""

from __future__ import annotations


def _who(actor) -> str:
    return getattr(actor, "username", None) or "system"


class ReservationNarrator:
    @staticmethod
    def created(*, asset_name: str, scheduled_start, scheduled_end, accountable_name: str) -> str:
        return (
            f"Reservation created for {asset_name}, "
            f"{scheduled_start:%d %b %Y %H:%M} - {scheduled_end:%d %b %Y %H:%M}. "
            f"Accountable: {accountable_name}."
        )

    @staticmethod
    def confirmed(*, actor, conflict_acknowledged: bool) -> str:
        note = " (confirmed despite an overlapping booking, acknowledged)" if conflict_acknowledged else ""
        return f"Reservation confirmed by {_who(actor)}{note}."

    @staticmethod
    def cancelled(*, actor, reason: str) -> str:
        return f"Reservation cancelled by {_who(actor)} — \"{reason}\"."

    @staticmethod
    def no_show(*, actor) -> str:
        return f"Marked as a no-show by {_who(actor)}."

    @staticmethod
    def user_checked_out(*, actor, condition: str | None) -> str:
        cond = f" Condition reported: {condition}." if condition else ""
        return f"Self-service checkout by {_who(actor)}.{cond}"

    @staticmethod
    def dispatcher_checkout_verified(*, actor, condition: str | None) -> str:
        cond = f" Condition: {condition}." if condition else ""
        return f"Checkout verified by {_who(actor)}.{cond}"

    @staticmethod
    def user_checked_in(*, actor, condition: str | None) -> str:
        cond = f" Condition reported: {condition}." if condition else ""
        return f"Self-service return by {_who(actor)}.{cond}"

    @staticmethod
    def dispatcher_return_verified(*, actor, condition: str | None) -> str:
        cond = f" Condition: {condition}." if condition else ""
        return f"Return verified by {_who(actor)}.{cond}"

    @staticmethod
    def promoted_to_dispatch(*, dispatch_id: int) -> str:
        return f"Attached to Dispatch #{dispatch_id}."
