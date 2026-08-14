"""Factory: the whole atomic PO build — header, Event, lines, allocations.

A PO IS ALWAYS CREATED AS DRAFT, NEVER DIRECTLY AS PLACED (D52). Creating the
paperwork is not sending it. The legacy from_dict factory created POs already
Ordered, which meant there was no state in which a PO could be reviewed before
the vendor was told; placing is a separate deliberate act.

There is no create_vendor step here — the vendor is an existing
procurement.Vendor; a missing one must be registered separately before a PO
can reference it.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from app.events.models import Event, EventStatus, EventType
from app.procurement.control_layer.managers.purchase_order_cost_manager import (
    PurchaseOrderCostManager,
)
from app.procurement.control_layer.managers.purchase_order_demand_link_manager import (
    PurchaseOrderDemandLinkManager,
)
from app.procurement.control_layer.managers.purchase_order_line_manager import (
    PurchaseOrderLineManager,
)
from app.procurement.control_layer.narrators.purchase_order_narrator import (
    PurchaseOrderNarrator,
)
from app.procurement.models import PartDemand, PurchaseOrder, PurchaseOrderStatus
from app.procurement.presentation_layer.tools.po_events import (
    PurchaseOrderEventEmitter,
    PurchaseOrderEventPayload,
    PurchaseOrderEventType,
)


class PurchaseOrderFactory:
    @classmethod
    def generate_po_number(cls) -> str:
        """Format PO-<YYYY-MM-DD>-<8 hex>, carried forward from the legacy
        generator, which worked."""
        today = timezone.now().date().isoformat()
        return f"PO-{today}-{uuid.uuid4().hex[:8]}"

    @classmethod
    def create_from_draft(cls, *, draft, actor=None) -> PurchaseOrder:
        """Build a complete PO from the wizard's session-backed draft, in ONE
        transaction. If any step fails, no PO exists.

        The draft is not a database row, deliberately: a half-built PO in the
        database would be visible to other Buyers, would need a status value
        meaning "not really a PO yet", and would leave orphans when abandoned.
        Draft status means "a real PO not yet sent to the vendor", which is a
        different and legitimate thing.
        """
        with transaction.atomic():
            po_number = cls.generate_po_number()

            # One Event per PO for its whole lifetime (D17) — not one per
            # status change. It carries the status history as machine comments
            # (D18) and the document library via its attachments (D19).
            event = Event.objects.create(
                domain_id=draft.domain_id,
                title=f"Purchase order {po_number}",
                description=draft.notes,
                event_type=EventType.INVENTORY,
                status=EventStatus.IN_PROGRESS,
                created_by=actor,
                updated_by=actor,
            )

            purchase_order = PurchaseOrder.objects.create(
                po_number=po_number,
                vendor_id=draft.vendor_id,
                vendor_contact=draft.vendor_contact,
                domain_id=draft.domain_id,
                status=PurchaseOrderStatus.DRAFT,
                order_date=draft.order_date or timezone.now().date(),
                expected_delivery_date=draft.expected_delivery_date,
                shipping_cost=draft.shipping_cost,
                tax_amount=draft.tax_amount,
                other_amount=draft.other_amount,
                notes=draft.notes,
                event=event,
                created_by=actor,
                updated_by=actor,
            )

            PurchaseOrderNarrator.post(
                purchase_order=purchase_order,
                message=PurchaseOrderNarrator.created(
                    po_number=po_number, vendor_name=str(purchase_order.vendor)
                ),
                actor=actor,
            )

            affected_demand_ids: list[int] = []
            for draft_line in draft.lines:
                line, _warning = PurchaseOrderLineManager.add_line(
                    purchase_order=purchase_order,
                    part_id=draft_line.part_id,
                    quantity_ordered=draft_line.quantity_ordered,
                    unit_cost=draft_line.unit_cost,
                    expected_delivery_date=draft_line.expected_delivery_date,
                    notes=draft_line.notes,
                    unit_cost_source=draft_line.unit_cost_source,
                    unit_cost_confidence=draft_line.unit_cost_confidence,
                    unit_cost_asserted_at=draft_line.unit_cost_asserted_at,
                    actor=actor,
                    commit=False,
                )
                for allocation in draft_line.allocations:
                    demand = PartDemand.objects.get(pk=allocation.demand_id)
                    PurchaseOrderDemandLinkManager.allocate(
                        line=line,
                        demand=demand,
                        quantity_allocated=allocation.quantity_allocated,
                        actor=actor,
                        auto_approve=allocation.auto_approve,
                        allow_raise_request=allocation.raise_request,
                        commit=False,
                    )
                    if allocation.raise_request:
                        # D28's explicit choice, already resolved in the wizard.
                        from app.procurement.control_layer.managers.part_demand_quantity_manager import (
                            PartDemandQuantityManager,
                        )

                        PartDemandQuantityManager.raise_requested_quantity(
                            demand=demand,
                            new_quantity=demand.purchased_qty,
                            actor=actor,
                            commit=False,
                        )
                    affected_demand_ids.append(demand.pk)

            PurchaseOrderCostManager.recompute(
                purchase_order=purchase_order, actor=actor, commit=False
            )
            purchase_order.save()

            PurchaseOrderEventEmitter.emit(
                PurchaseOrderEventPayload(
                    event_type=PurchaseOrderEventType.PO_CREATED,
                    purchase_order_id=purchase_order.pk,
                    po_number=purchase_order.po_number,
                    status=purchase_order.status,
                    occurred_at=timezone.now(),
                    actor_id=getattr(actor, "pk", None),
                    affected_demand_ids=tuple(affected_demand_ids),
                )
            )

        return purchase_order

    @classmethod
    def create(
        cls,
        *,
        vendor_id: int,
        domain_id: int,
        actor=None,
        vendor_contact: str = "",
        order_date=None,
        expected_delivery_date=None,
        shipping_cost: Decimal | None = None,
        tax_amount: Decimal | None = None,
        other_amount: Decimal | None = None,
        notes: str = "",
    ) -> PurchaseOrder:
        """Create an empty Draft PO. A PO with zero linked demands is fully
        valid (D14) — proactive and bulk restocking is in scope."""
        from app.procurement.control_layer.adapters.purchase_order_draft_adaptor import (
            PurchaseOrderDraft,
        )

        draft = PurchaseOrderDraft(
            vendor_id=vendor_id,
            domain_id=domain_id,
            vendor_contact=vendor_contact,
            order_date=order_date,
            expected_delivery_date=expected_delivery_date,
            shipping_cost=shipping_cost,
            tax_amount=tax_amount,
            other_amount=other_amount,
            notes=notes,
            lines=[],
        )
        return cls.create_from_draft(draft=draft, actor=actor)
