"""Guard type: Policy. One of the three rules permissions cannot express
(dispatching_starter_kit/5_roles_and_permissions.md §4.5): the dispatcher
verifying a handover must not be the same person who performed the
self-service side — the two-track handover exists to catch discrepancies,
and one person doing both defeats it."""

from __future__ import annotations


class VerifierDistinctPolicy:
    @classmethod
    def check(cls, *, verifier, self_service_actor_id: int | None) -> None:
        verifier_id = getattr(verifier, "pk", None)
        if self_service_actor_id is not None and verifier_id == self_service_actor_id:
            raise ValueError(
                "The handover verifier must not be the same person who performed "
                "the self-service side."
            )
