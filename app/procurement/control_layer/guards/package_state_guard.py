"""Guard type: StateMachine. Legal Package.status transitions.

Fails open per D13, like the demand axes: package status is very high volume
and ideally machine-fed, so a guard that cannot decide must not stop the feed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models import PackageStatus

PACKAGE_TRANSITIONS: dict[str, frozenset[str]] = {
    PackageStatus.AWAITING_SHIPMENT: frozenset(
        {PackageStatus.SHIPPED, PackageStatus.BACKORDERED, PackageStatus.LOST, PackageStatus.CANCELLED}
    ),
    # The vendor says it's delayed/out of stock. Re-enters the chain at
    # Shipped once it moves, same as a found Lost package.
    PackageStatus.BACKORDERED: frozenset(
        {PackageStatus.SHIPPED, PackageStatus.LOST, PackageStatus.CANCELLED}
    ),
    PackageStatus.SHIPPED: frozenset(
        {
            PackageStatus.DELIVERED_TO_DEPOT,
            PackageStatus.DELIVERED_TO_LOCAL,
            PackageStatus.LOST,
            PackageStatus.CANCELLED,
        }
    ),
    PackageStatus.DELIVERED_TO_DEPOT: frozenset(
        {PackageStatus.DELIVERED_TO_LOCAL, PackageStatus.LOST, PackageStatus.CANCELLED}
    ),
    PackageStatus.DELIVERED_TO_LOCAL: frozenset({PackageStatus.ACCEPTED}),
    # Accepted means inspected and intact. It does NOT mean stocked — stocked
    # is intake's word, and intake is not built.
    PackageStatus.ACCEPTED: frozenset(),
    # A package found after being written off re-enters the chain.
    PackageStatus.LOST: frozenset({PackageStatus.SHIPPED}),
    PackageStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class PackageVerdict:
    allowed: bool
    reason: str = ""
    flagged: bool = False


class PackageStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> PackageVerdict:
        if from_status == to_status:
            return PackageVerdict(
                allowed=False, reason="The package is already in that state."
            )
        legal = PACKAGE_TRANSITIONS.get(from_status)
        if legal is None:
            # Undecidable — allow and flag rather than blocking a shipment feed.
            return PackageVerdict(
                allowed=True,
                reason=f"Unknown package status '{from_status}' — allowed and flagged.",
                flagged=True,
            )
        if to_status not in legal:
            return PackageVerdict(
                allowed=False,
                reason=f"A '{from_status}' package cannot move to '{to_status}'.",
            )
        return PackageVerdict(allowed=True)
