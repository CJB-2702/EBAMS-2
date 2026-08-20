"""Guard type: Policy. One of the three rules permissions cannot express
(dispatching_starter_kit/5_roles_and_permissions.md §4.5): self-service
checkout and return require being the accountable person on that booking —
holding the Reservation-Self-Service permission is not enough.

One documented escape: a dispatch manager may record the user-reported side
on the accountable person's behalf (``on_behalf=True``). The caller decides
who qualifies — this guard only honours the flag. VerifierDistinctPolicy
still refuses to let that same person verify the entry they just made, which
is the constraint the two-track handover actually depends on.
"""

from __future__ import annotations


class AccountablePersonPolicy:
    @classmethod
    def check(cls, *, reservation, actor, on_behalf: bool = False) -> None:
        actor_id = getattr(actor, "pk", None)
        if actor_id is None:
            raise ValueError(
                "Only the accountable person on this reservation may perform "
                "self-service handover."
            )
        if reservation.accountable_person_id == actor_id or on_behalf:
            return
        raise ValueError(
            "Only the accountable person on this reservation may perform "
            "self-service handover."
        )
