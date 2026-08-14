"""Manager: allocate, de-link, and release demand allocations.

DE-LINK vs RELEASE — the distinction matters and the words are not
interchangeable:

  de-link  The Buyer changed their mind about this pairing. Soft delete.
           purchasing_state does NOT roll backward: Purchased means money
           moved, and de-linking does not un-move it.
  release  The PO was cancelled and the vendor is not shipping.
           is_active = False, readable as history. purchased_qty recomputes
           across active rows only, freeing the Buyer to re-allocate.

Cancelling a whole LINE is the one case that does roll purchasing_state
backward (D56), because there the thing that spent the money is gone.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.guards.purchase_order_demand_link_guard import (
    PurchaseOrderDemandLinkValidator,
)
from app.procurement.control_layer.managers.part_demand_quantity_manager import (
    PartDemandQuantityManager,
)
from app.procurement.control_layer.managers.part_demand_state_manager import (
    PartDemandStateManager,
)
from app.procurement.control_layer.narrators.part_demand_narrator import (
    PartDemandNarrator,
)
from app.procurement.control_layer.narrators.purchase_order_narrator import (
    PurchaseOrderNarrator,
)
from app.procurement.models import (
    DemandDimension,
    DemandState,
    PartDemand,
    PurchaseOrderDemandLink,
    PurchaseOrderStatus,
    PurchasingState,
    ShipmentState,
)


class PurchaseOrderDemandLinkManager:
    @classmethod
    def allocate(
        cls,
        *,
        line,
        demand: PartDemand,
        quantity_allocated: Decimal,
        actor=None,
        auto_approve: bool = True,
        allow_raise_request: bool = False,
        notes: str = "",
        commit: bool = True,
    ) -> PurchaseOrderDemandLink:
        """Claim part of a PO line as fulfilling a specific demand.

        auto_approve implements D42: creating a link auto-promotes
        demand_state -> Approved by default. This is NOT a shortcut around Gate
        1 — Gate 1 (D9) is unchanged and still blocks purchasing_state from
        leaving unset without approval. What changes is how approval is usually
        reached: in real usage Purchasing routinely acts before an Approver
        signs off, directed through outside channels, and hard-blocking the
        Buyer's link would stop daily work waiting on a step the organization
        has already decided informally.

        A Buyer who wants the strict approve-first process for a given item
        passes auto_approve=False; Gate 1 then holds and purchasing_state stays
        unset until an Approver actually acts.
        """
        existing = PurchaseOrderDemandLink.objects.filter(
            part_demand=demand, purchase_order_line=line, deleted_at__isnull=True
        ).first()

        PurchaseOrderDemandLinkValidator.check(
            demand=demand,
            line=line,
            quantity_allocated=quantity_allocated,
            existing_link=existing,
            allow_raise_request=allow_raise_request,
        )

        if existing is not None:
            existing.quantity_allocated = quantity_allocated
            existing.is_active = True
            existing.notes = notes or existing.notes
            existing.updated_by = actor
            existing.save(
                update_fields=[
                    "quantity_allocated",
                    "is_active",
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )
            link = existing
        else:
            link = PurchaseOrderDemandLink.objects.create(
                part_demand=demand,
                purchase_order_line=line,
                quantity_allocated=quantity_allocated,
                notes=notes,
                created_by=actor,
                updated_by=actor,
            )

        cls._auto_update_line_quantity_if_needed(
            line=line, actor=actor, commit=commit
        )

        purchase_order = line.purchase_order

        # D42's auto-promotion. The resulting journal row records the Buyer as
        # actor with is_system_generated=False — they did approve it, by
        # linking it.
        if auto_approve and demand.demand_state in {
            DemandState.PROJECTED,
            DemandState.REQUIRED,
            DemandState.REJECTED,
        }:
            PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.DEMAND,
                to_stage=DemandState.APPROVED,
                actor=actor,
                notes=PartDemandNarrator.auto_approved_by_link(
                    po_number=purchase_order.po_number
                ),
                raise_on_refusal=False,
                commit=False,
            )

        PartDemandQuantityManager.refresh_purchased_qty(
            demand=demand, actor=actor, commit=commit
        )

        # A demand linked to an already-placed PO is, by definition, already
        # bought — propagate immediately rather than waiting for a status move
        # that already happened (D40).
        if purchase_order.status in {
            PurchaseOrderStatus.PLACED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED,
        }:
            PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.PURCHASING,
                to_stage=PurchasingState.PURCHASED,
                actor=actor,
                notes=PartDemandNarrator.propagated_from_purchase_order(
                    po_number=purchase_order.po_number
                ),
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.SHIPMENT,
                to_stage=ShipmentState.REQUEST_RECEIVED_BY_VENDOR,
                actor=actor,
                notes=PartDemandNarrator.propagated_from_purchase_order(
                    po_number=purchase_order.po_number
                ),
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )

        PurchaseOrderNarrator.post(
            purchase_order=purchase_order,
            message=PurchaseOrderNarrator.allocation_added(
                demand_id=demand.pk,
                line_number=line.line_number,
                quantity=quantity_allocated,
            ),
            actor=actor,
        )

        # Adding a second demand to a line moves it from attributable to a
        # shared demand session, after which no per-demand arrival figure
        # exists for either demand on that line. That is a real consequence of
        # an ordinary Buyer action, and it must be said at the moment it
        # happens rather than discovered later in a report.
        active_count = line.allocations.filter(
            is_active=True, deleted_at__isnull=True
        ).count()
        if active_count >= 2:
            PurchaseOrderNarrator.post(
                purchase_order=purchase_order,
                message=PurchaseOrderNarrator.shared_session_formed(
                    line_number=line.line_number, member_count=active_count
                ),
                actor=actor,
            )

        return link

    @classmethod
    def delink(cls, *, link: PurchaseOrderDemandLink, actor=None, commit: bool = True) -> None:
        """The Buyer's alternative to cancellation (D4). A Buyer never cancels
        a demand; they undo the allocation instead."""
        from django.utils import timezone

        purchase_order = link.purchase_order_line.purchase_order
        demand = link.part_demand

        PurchaseOrderNarrator.post_with_snapshot(
            purchase_order=purchase_order,
            message=PurchaseOrderNarrator.allocation_removed(
                demand_id=demand.pk, line_number=link.purchase_order_line.line_number
            ),
            row=link,
            actor=actor,
        )

        link.deleted_at = timezone.now()
        link.updated_by = actor
        link.save(update_fields=["deleted_at", "updated_by", "updated_at"])

        PartDemandQuantityManager.refresh_purchased_qty(
            demand=demand, actor=actor, commit=commit
        )
        # purchasing_state deliberately does NOT roll backward here.

    @classmethod
    def release_for_purchase_order(
        cls, *, purchase_order, actor=None, commit: bool = True
    ) -> int:
        """Release every allocation on a cancelled PO.

        Nothing physical is reversed: package lines already accepted against
        the PO's lines keep their quantity_accepted. What arrived, arrived,
        regardless of what happens to the PO administratively afterward.
        """
        links = PurchaseOrderDemandLink.objects.filter(
            purchase_order_line__purchase_order=purchase_order,
            is_active=True,
            deleted_at__isnull=True,
        ).select_related("part_demand")

        count = 0
        for link in links:
            link.is_active = False
            link.updated_by = actor
            link.save(update_fields=["is_active", "updated_by", "updated_at"])
            PartDemandQuantityManager.refresh_purchased_qty(
                demand=link.part_demand, actor=actor, commit=commit
            )
            count += 1
        return count

    @classmethod
    def remove_for_line(cls, *, line, actor=None, commit: bool = True) -> int:
        """D56: cancelling a PO line removes its demand links and resets those
        demands' purchasing_state to unset.

        Not configurable, not prompted. The demands return to "no purchasing
        decision has been made," which is accurate once the thing that was
        going to buy them is gone. demand_state is deliberately untouched — the
        need may still be real and buyable elsewhere; a Requester or Approver
        cancels it manually later if it is not (D4).
        """
        from django.utils import timezone

        purchase_order = line.purchase_order
        links = line.allocations.filter(deleted_at__isnull=True).select_related(
            "part_demand"
        )

        count = 0
        for link in links:
            demand = link.part_demand
            link.deleted_at = timezone.now()
            link.is_active = False
            link.updated_by = actor
            link.save(
                update_fields=["deleted_at", "is_active", "updated_by", "updated_at"]
            )

            PartDemandQuantityManager.refresh_purchased_qty(
                demand=demand, actor=actor, commit=commit
            )
            PartDemandStateManager.transition(
                demand=demand,
                dimension=DemandDimension.PURCHASING,
                to_stage="",
                actor=actor,
                notes=PartDemandNarrator.purchasing_reset_by_line_cancellation(
                    po_number=purchase_order.po_number
                ),
                is_system_generated=True,
                raise_on_refusal=False,
                commit=False,
            )
            count += 1
        return count

    @staticmethod
    def _auto_update_line_quantity_if_needed(*, line, actor=None, commit: bool = True) -> None:
        """Auto-update line quantity_ordered to be the sum of allocations if it's
        below the sum. This ensures the ordered quantity always covers the
        allocated total."""
        from django.db.models import Sum
        from app.procurement.control_layer.managers.purchase_order_cost_manager import (
            PurchaseOrderCostManager,
        )

        total_allocated = (
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line=line, is_active=True, deleted_at__isnull=True
            ).aggregate(total=Sum("quantity_allocated"))["total"]
            or Decimal("0")
        )

        if total_allocated > line.quantity_ordered:
            line.quantity_ordered = total_allocated
            line.updated_by = actor
            line.save(update_fields=["quantity_ordered", "updated_by", "updated_at"])
            PurchaseOrderCostManager.recompute(
                purchase_order=line.purchase_order, actor=actor, commit=commit
            )
