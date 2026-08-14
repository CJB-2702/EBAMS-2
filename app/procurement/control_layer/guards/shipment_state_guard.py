"""Guard type: StateMachine. Legal Shipment.status transitions.

Fails open per D13, like the demand axes: shipment status is very high volume
and ideally machine-fed, so a guard that cannot decide must not stop the feed.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.procurement.models import ShipmentStatus

SHIPMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    ShipmentStatus.AWAITING_SHIPMENT: frozenset(
        {ShipmentStatus.SHIPPED, ShipmentStatus.BACKORDERED, ShipmentStatus.LOST, ShipmentStatus.CANCELLED}
    ),
    # The vendor says it's delayed/out of stock. Re-enters the chain at
    # Shipped once it moves, same as a found Lost shipment.
    ShipmentStatus.BACKORDERED: frozenset(
        {ShipmentStatus.SHIPPED, ShipmentStatus.LOST, ShipmentStatus.CANCELLED}
    ),
    ShipmentStatus.SHIPPED: frozenset(
        {
            ShipmentStatus.DELIVERED_TO_DEPOT,
            ShipmentStatus.DELIVERED_TO_LOCAL,
            ShipmentStatus.LOST,
            ShipmentStatus.CANCELLED,
        }
    ),
    ShipmentStatus.DELIVERED_TO_DEPOT: frozenset(
        {ShipmentStatus.DELIVERED_TO_LOCAL, ShipmentStatus.LOST, ShipmentStatus.CANCELLED}
    ),
    ShipmentStatus.DELIVERED_TO_LOCAL: frozenset({ShipmentStatus.ACCEPTED}),
    # Accepted means inspected and intact. It does NOT mean stocked — stocked
    # is intake's word, and intake is not built.
    ShipmentStatus.ACCEPTED: frozenset(),
    # A shipment found after being written off re-enters the chain.
    ShipmentStatus.LOST: frozenset({ShipmentStatus.SHIPPED}),
    ShipmentStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class ShipmentVerdict:
    allowed: bool
    reason: str = ""
    flagged: bool = False


class ShipmentStateMachine:
    @classmethod
    def check(cls, *, from_status: str, to_status: str) -> ShipmentVerdict:
        if from_status == to_status:
            return ShipmentVerdict(
                allowed=False, reason="The shipment is already in that state."
            )
        legal = SHIPMENT_TRANSITIONS.get(from_status)
        if legal is None:
            # Undecidable — allow and flag rather than blocking a shipment feed.
            return ShipmentVerdict(
                allowed=True,
                reason=f"Unknown shipment status '{from_status}' — allowed and flagged.",
                flagged=True,
            )
        if to_status not in legal:
            return ShipmentVerdict(
                allowed=False,
                reason=f"A '{from_status}' shipment cannot move to '{to_status}'.",
            )
        return ShipmentVerdict(allowed=True)
