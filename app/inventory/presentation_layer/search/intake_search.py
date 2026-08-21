"""Search: reads for the Intake dashboard and Auto Intake portal.

Same D84 boundary `InventoryShipmentSearch` already draws for the Shipments
mirror: plain queryset reads against procurement's own `Shipment`/
`ShipmentLine` tables, domain-scoped, no import of procurement's
presentation or control layer.
"""

from __future__ import annotations

from django.db.models import Count, F, Q, QuerySet

from app.inventory.models.intake.enums import AllocationCondition, IntakeSessionStatus
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


class ExternalExcessAllocationSearch:
    """Cross-session unlinked stock — read side, and the seed of the
    allocation portal's global scope (intake_portal_workflow.md §7.3).

    Finds unlinked (`shipment_line=NULL`, `condition=GOOD`) allocations for
    a part sitting in some OTHER live session. Excess counted in session 1
    can fill a shortage discovered in session 2; without a read that reaches
    across sessions that stock sits quarantined forever while somebody
    re-orders parts already on the shelf.

    Read-only. Its former write partner (`pull_external_allocation`) was
    deleted with the reconciliation surface — Phase 2's allocation portal
    owns the linking write, under the over-allocation ban (§7.2).
    """

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
