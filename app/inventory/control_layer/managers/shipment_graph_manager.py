"""Manager: the connected component of sessions and shipments reachable from
one intake session (tech_debt/intake_shipment_graph_closure.md §4).

Sessions and shipments form a BIPARTITE GRAPH. A session receiving against two
shipments creates an edge between them, and those edges are transitive, so
shipments become coupled to shipments no single session ever touches:

    Session 1 -> A, B        Session 2 -> B, C
    Nothing links A to C, but B is in both, so A and C are coupled.

WHAT THE GRAPH BUYS YOU IS BLAST RADIUS, NOT CORRECTNESS. It answers "who else
is affected by this?", never "is something wrong?". Nothing can be wrong:
over-allocation is impossible (§7.2) and there is no sign-off to propagate
(§7.1), so the only remaining symptom is that a reader may be under-informed.
Hold onto that distinction — it is what makes the deferral safe.

READ-ONLY. No writes, no schema, no migration. One closure traversal on one
page load.

The discrepancy report renders this ONLY when the closure reaches beyond the
current session's own shipments. Most sessions are an isolated component and
nobody should ever see it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.inventory.models.intake.enums import IntakeSessionStatus
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.intake_session_shipment_link import (
    IntakeSessionShipmentLink,
)


@dataclass(frozen=True)
class ShipmentClosureStruct:
    origin_session_id: int
    session_ids: tuple[int, ...] = field(default_factory=tuple)
    shipment_ids: tuple[int, ...] = field(default_factory=tuple)
    own_shipment_ids: tuple[int, ...] = field(default_factory=tuple)
    edges: tuple[tuple[int, int], ...] = field(default_factory=tuple)

    @property
    def reaches_beyond_session(self) -> bool:
        """The render trigger (§4.1). True when another session shares one of
        our shipments, or when the closure dragged in a shipment we never
        touch."""
        return len(self.session_ids) > 1 or set(self.shipment_ids) != set(
            self.own_shipment_ids
        )

    @property
    def foreign_session_ids(self) -> tuple[int, ...]:
        return tuple(s for s in self.session_ids if s != self.origin_session_id)

    @property
    def foreign_shipment_ids(self) -> tuple[int, ...]:
        own = set(self.own_shipment_ids)
        return tuple(s for s in self.shipment_ids if s not in own)


class ShipmentGraphManager:
    @classmethod
    def closure_for(cls, *, session) -> ShipmentClosureStruct:
        """Breadth-first alternation between sessions and shipments until
        nothing new appears. Cancelled and soft-deleted sessions are not
        nodes — they contribute no allocations, so they couple nothing."""
        live_links = IntakeSessionShipmentLink.objects.filter(
            deleted_at__isnull=True,
            intake_session__deleted_at__isnull=True,
        ).exclude(intake_session__status=IntakeSessionStatus.CANCELLED)

        own_shipment_ids = set(
            live_links.filter(intake_session_id=session.pk).values_list(
                "shipment_id", flat=True
            )
        )

        session_ids = {session.pk}
        shipment_ids = set(own_shipment_ids)
        frontier_shipments = set(own_shipment_ids)

        while frontier_shipments:
            new_sessions = set(
                live_links.filter(shipment_id__in=frontier_shipments).values_list(
                    "intake_session_id", flat=True
                )
            ) - session_ids
            if not new_sessions:
                break
            session_ids |= new_sessions

            new_shipments = set(
                live_links.filter(intake_session_id__in=new_sessions).values_list(
                    "shipment_id", flat=True
                )
            ) - shipment_ids
            shipment_ids |= new_shipments
            frontier_shipments = new_shipments

        edges = tuple(
            sorted(
                live_links.filter(intake_session_id__in=session_ids).values_list(
                    "intake_session_id", "shipment_id"
                )
            )
        )
        return ShipmentClosureStruct(
            origin_session_id=session.pk,
            session_ids=tuple(sorted(session_ids)),
            shipment_ids=tuple(sorted(shipment_ids)),
            own_shipment_ids=tuple(sorted(own_shipment_ids)),
            edges=edges,
        )

    @classmethod
    def labels(cls, *, closure: ShipmentClosureStruct) -> dict:
        """Display names for the diagram, fetched in two queries."""
        from app.procurement.models import Shipment

        sessions = dict(
            IntakeSession.objects.filter(pk__in=closure.session_ids).values_list(
                "pk", "status"
            )
        )
        shipments = dict(
            Shipment.objects.filter(pk__in=closure.shipment_ids).values_list(
                "pk", "shipment_number"
            )
        )
        return {"sessions": sessions, "shipments": shipments}
