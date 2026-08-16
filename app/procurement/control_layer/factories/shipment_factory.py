"""Factory: creates a Shipment and its lines with copied PO links."""

from __future__ import annotations

import uuid

from django.db import transaction
from django.utils import timezone

from app.events.models import Event, EventStatus, EventType
from app.procurement.control_layer.managers.shipment_line_manager import (
    ShipmentLineManager,
)
from app.procurement.control_layer.managers.shipment_status_manager import (
    ShipmentStatusManager,
)
from app.procurement.control_layer.narrators.shipment_narrator import ShipmentNarrator
from app.procurement.models import Shipment, ShipmentStatus


class ShipmentFactory:
    @classmethod
    def generate_shipment_number(cls) -> str:
        today = timezone.now().date().isoformat()
        return f"SHP-{today}-{uuid.uuid4().hex[:8]}"

    @classmethod
    def create(
        cls,
        *,
        domain=None,
        purchase_order=None,
        lines: list[dict] | None = None,
        actor=None,
        shipment_id: str = "",
        carrier: str = "",
        shipped_date=None,
        expected_arrival_date=None,
        notes: str = "",
        status: str = ShipmentStatus.AWAITING_SHIPMENT,
    ) -> Shipment:
        """A shipment is created against a purchase order OR received
        reactively with none yet on file (D71/D73 reverses D59's "never
        free-floating" rule).

        ``domain`` is required when ``purchase_order`` is None — a shipment
        cannot exist without SOME domain to fence it. When a PO is supplied,
        its domain is copied and an explicit ``domain`` must either be omitted
        or agree with it.

        Each line dict is {"part_id": int, "quantity": Decimal}, optionally
        carrying {"allocations": [{"purchase_order_line": PurchaseOrderLine,
        "quantity": Decimal}]}.

        WITHOUT allocations, lines copy their PO link from the header
        automatically; a line whose part matches no active line on the header
        PO is recorded with a null PO line rather than refused. WITH them,
        copy-on-create is suppressed for that line and exactly the supplied
        allocations are written — the caller has already decided, and a guess
        laid down first would consume the headroom their decision needs. The
        allocations may point at any order line, including one on a different
        PO than the header; that is drift, it is legal, and the mixed-assignment
        flag records it.
        """
        if purchase_order is not None:
            domain = domain or purchase_order.domain
        if domain is None:
            raise ValueError(
                "ShipmentFactory.create requires a domain when no purchase_order "
                "is supplied."
            )

        with transaction.atomic():
            shipment_number = cls.generate_shipment_number()

            event = Event.objects.create(
                domain_id=domain.pk,
                title=f"Shipment {shipment_number}",
                description=notes,
                event_type=EventType.INVENTORY,
                status=EventStatus.IN_PROGRESS,
                created_by=actor,
                updated_by=actor,
            )

            shipment = Shipment.objects.create(
                purchase_order=purchase_order,
                domain=domain,
                event=event,
                shipment_number=shipment_number,
                shipment_id=shipment_id,
                carrier=carrier,
                status=status,
                shipped_date=shipped_date,
                expected_arrival_date=expected_arrival_date,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )

            for raw_line in lines or []:
                allocations = raw_line.get("allocations") or []
                line = ShipmentLineManager.add_line(
                    shipment=shipment,
                    part_id=raw_line["part_id"],
                    quantity=raw_line["quantity"],
                    actor=actor,
                    auto_link=not allocations,
                    commit=False,
                )
                for allocation in allocations:
                    ShipmentLineManager.allocate(
                        line=line,
                        purchase_order_line=allocation["purchase_order_line"],
                        quantity=allocation["quantity"],
                        actor=actor,
                        commit=False,
                    )

            ShipmentStatusManager.refresh_mixed_po_assignments(
                shipment=shipment, actor=actor, commit=True
            )
            ShipmentStatusManager.propagate_shipment_state(
                shipment=shipment, actor=actor
            )

            ShipmentNarrator.post(
                shipment=shipment,
                message=ShipmentNarrator.created(
                    shipment_number=shipment.shipment_number,
                    line_count=len(lines or []),
                    purchase_order_number=(
                        purchase_order.po_number if purchase_order else ""
                    ),
                ),
                actor=actor,
            )

        return shipment
