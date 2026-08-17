"""Search: reads for the Intake dashboard and Auto Intake portal.

Same D84 boundary `InventoryShipmentSearch` already draws for the Shipments
mirror: plain queryset reads against procurement's own `Shipment`/
`ShipmentLine` tables, domain-scoped, no import of procurement's
presentation or control layer.
"""

from __future__ import annotations

from django.db.models import Count, F, Q, QuerySet

from app.inventory.models.intake.enums import (
    AllocationCondition,
    IntakeSessionStatus,
    ReconciliationStatus,
)
from app.inventory.models.intake.intake_session import IntakeSession
from app.inventory.models.intake.item_allocation import ItemAllocation
from app.procurement.models import Shipment, ShipmentLine, ShipmentStatus


class UnfulfilledShipmentSearch:
    @classmethod
    def index_list(cls, *, domain_ids, q: str = "") -> QuerySet[Shipment]:
        """Shipments still worth receiving against: not cancelled/lost, and
        at least one active line whose shipped quantity outruns everything
        accepted against it across every CLOSED intake session so far."""
        qs = (
            Shipment.objects.filter(domain_id__in=domain_ids, deleted_at__isnull=True)
            .exclude(status__in=[ShipmentStatus.CANCELLED, ShipmentStatus.LOST])
            .select_related("purchase_order", "purchase_order__vendor")
            .annotate(
                open_line_count=Count(
                    "lines",
                    filter=Q(lines__deleted_at__isnull=True)
                    & (
                        Q(lines__quantity_accepted__isnull=True)
                        | Q(lines__quantity_accepted__lt=F("lines__quantity"))
                    ),
                    distinct=True,
                ),
            )
            .filter(open_line_count__gt=0)
        )
        if q:
            qs = qs.filter(
                Q(shipment_number__icontains=q)
                | Q(shipment_id__icontains=q)
                | Q(purchase_order__po_number__icontains=q)
            )
        return qs.order_by("-created_at")

    @classmethod
    def lines_for_shipment(cls, *, shipment_id: int) -> QuerySet[ShipmentLine]:
        return (
            ShipmentLine.objects.filter(
                shipment_id=shipment_id, deleted_at__isnull=True
            )
            .select_related("part")
            .order_by("id")
        )


class IntakeSessionSearch:
    @classmethod
    def recent(cls, *, warehouse_ids=None, limit: int = 25) -> QuerySet[IntakeSession]:
        qs = IntakeSession.objects.filter(deleted_at__isnull=True).select_related(
            "operator", "warehouse", "room"
        )
        if warehouse_ids is not None:
            qs = qs.filter(warehouse_id__in=warehouse_ids)
        return qs.order_by("-started_at")[:limit]


class PartReconciliationSearch:
    """Reconciliation Hub reads — the manager queue of sessions carrying
    `PartReconciliationSession` parents, plus per-session summaries.

    Severity/unresolved counts are derived fresh from live
    `PartReconciliationLine` aggregates on every call (never cached on a
    model field, per the phase brief) — `intake_session_id` cardinality here
    is small enough (one Hub page load) that computing this in Python next
    to the ORM read is simpler than a correlated-subquery annotation.
    """

    @classmethod
    def hub_sessions(
        cls, *, status: str = "", has_unresolved_only: bool = False
    ) -> QuerySet[IntakeSession]:
        qs = (
            IntakeSession.objects.filter(
                deleted_at__isnull=True, reconciliations__deleted_at__isnull=True
            )
            .distinct()
            .select_related("operator", "warehouse", "room")
        )
        if status:
            qs = qs.filter(status=status)
        else:
            qs = qs.filter(status=IntakeSessionStatus.RECONCILING)
        if has_unresolved_only:
            qs = qs.filter(
                reconciliations__status=ReconciliationStatus.PENDING,
                reconciliations__deleted_at__isnull=True,
            )
        return qs.order_by("-started_at")

    @classmethod
    def summarize(cls, session: IntakeSession) -> dict:
        """Per-session queue-row summary: part count, pending count, and a
        shortage/overage/mixed severity chip derived by comparing each live
        child line's received total (allocated+rejected) against its
        expected quantity — never netted across lines (FD-9)."""
        parents = list(
            session.reconciliations.filter(deleted_at__isnull=True)
            .select_related("part")
            .prefetch_related("lines")
        )
        pending = [p for p in parents if p.status == ReconciliationStatus.PENDING]
        has_shortage = False
        has_overage = False
        for parent in parents:
            for line in parent.lines.all():
                if line.deleted_at is not None:
                    continue
                received = line.allocated_quantity + line.rejected_quantity
                if received < line.expected_quantity:
                    has_shortage = True
                elif received > line.expected_quantity:
                    has_overage = True
        if has_shortage and has_overage:
            severity = "mixed"
        elif has_overage:
            severity = "overage"
        elif has_shortage:
            severity = "shortage"
        else:
            severity = "none"
        return {
            "part_count": len(parents),
            "pending_count": len(pending),
            "severity": severity,
        }


class ExternalExcessAllocationSearch:
    """FD-26's cross-session excess pull — read side. Finds unlinked
    (`shipment_line=NULL`, `condition=GOOD`) allocations for a part sitting
    in some OTHER live session, so a manager reconciling a shortage in
    session A can pull one into session A via
    `IntakeContext.pull_external_allocation`. Deliberately simple per FD-26
    ("doesn't need to be fancy")."""

    @classmethod
    def for_part(cls, *, part_id: int, exclude_session_id: int) -> QuerySet[ItemAllocation]:
        return (
            ItemAllocation.objects.filter(
                part_id=part_id,
                shipment_line__isnull=True,
                condition=AllocationCondition.GOOD,
                deleted_at__isnull=True,
            )
            .exclude(intake_session_id=exclude_session_id)
            .select_related("intake_session", "intake_session__warehouse")
            .order_by("-created_at")
        )
