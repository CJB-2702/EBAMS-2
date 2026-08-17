"""Manager: line add / edit / cancel / reorder, and the D57 audit snapshot.

LINES STAY EDITABLE AFTER PLACEMENT. Vendors substitute, short-ship, and
re-price after an order goes out, and the record should say what actually
happened rather than what was originally typed. The permissiveness is paid for
in audit rather than restriction: every mutation on a Placed-or-later PO posts
a machine comment carrying a JSON snapshot of the row as it stood before the
change, on edits and deletions alike.

The UI raises a soft warning; the control layer does not refuse. The one hard
stop is the quantity floor — a line's quantity_ordered cannot drop below what
has already been accepted against it, which is not a policy but a fact.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from app.procurement.control_layer.errors import (
    ProcurementValidationError,
    ReallocationRequired,
)
from app.procurement.control_layer.guards.purchase_order_line_guard import (
    PurchaseOrderLineValidator,
)
from app.procurement.control_layer.managers.graph_summary_manager import (
    GraphSummaryManager,
)
from app.procurement.control_layer.managers.purchase_order_cost_manager import (
    PurchaseOrderCostManager,
)
from app.procurement.control_layer.managers.purchase_order_demand_link_manager import (
    PurchaseOrderDemandLinkManager,
)
from app.procurement.control_layer.narrators.purchase_order_narrator import (
    PurchaseOrderNarrator,
)
from app.procurement.models import PurchaseOrderDemandLink, PurchaseOrderLine

#: Fields a caller may edit on an existing line.
EDITABLE_LINE_FIELDS = frozenset(
    {
        "quantity_ordered",
        "unit_cost",
        "expected_delivery_date",
        "notes",
        "part_id",
        "unit_cost_source",
        "unit_cost_confidence",
        "unit_cost_asserted_at",
    }
)


class PurchaseOrderLineManager:
    @classmethod
    def add_line(
        cls,
        *,
        purchase_order,
        part_id: int,
        quantity_ordered: Decimal,
        unit_cost: Decimal,
        expected_delivery_date=None,
        notes: str = "",
        # D85/D88 — the price chip's "Use this" and picker stamp these; blank
        # by default since a Buyer typing a plain number has stated no
        # provenance and none should be invented.
        unit_cost_source: str = "",
        unit_cost_confidence: str = "",
        unit_cost_asserted_at=None,
        actor=None,
        commit: bool = True,
    ) -> tuple[PurchaseOrderLine, object]:
        """Returns (line, duplicate_warning_or_None).

        The duplicate-part warning is SOFT (D58): the caller decides whether to
        surface it and proceed. Nothing hard-blocks.
        """
        PurchaseOrderLineValidator.check_new_line(
            quantity_ordered=quantity_ordered, unit_cost=unit_cost
        )
        warning = PurchaseOrderLineValidator.check_duplicate_part(
            purchase_order=purchase_order, part_id=part_id
        )

        next_number = (
            purchase_order.lines.aggregate(top=Max("line_number"))["top"] or 0
        ) + 1

        line = PurchaseOrderLine.objects.create(
            purchase_order=purchase_order,
            part_id=part_id,
            line_number=next_number,
            quantity_ordered=quantity_ordered,
            unit_cost=unit_cost,
            expected_delivery_date=expected_delivery_date,
            notes=notes,
            unit_cost_source=unit_cost_source,
            unit_cost_confidence=unit_cost_confidence,
            unit_cost_asserted_at=unit_cost_asserted_at,
            created_by=actor,
            updated_by=actor,
        )

        # D82 node-init: a line is always created with no demand link yet
        # (allocation is a separate subsequent step, even inside the PO
        # wizard's single transaction) — it always gets its own fresh
        # single-member graph here, later merged by
        # PurchaseOrderDemandLinkManager.allocate() once/if it is allocated.
        GraphSummaryManager.initialize_node(entity=line, actor=actor)

        PurchaseOrderCostManager.recompute(
            purchase_order=purchase_order, actor=actor, commit=commit
        )
        PurchaseOrderNarrator.post(
            purchase_order=purchase_order,
            message=PurchaseOrderNarrator.line_added(
                line_number=line.line_number,
                part_number=line.part.part_number,
                quantity=quantity_ordered,
            ),
            actor=actor,
        )
        return line, warning

    @classmethod
    def edit_line(
        cls, *, line: PurchaseOrderLine, changes: dict, actor=None, commit: bool = True
    ) -> PurchaseOrderLine:
        """Apply changes, posting the pre-state snapshot first.

        The snapshot is taken BEFORE mutation deliberately — the post-state is
        queryable from the row itself, so it is the pre-state that would
        otherwise be lost.
        """
        unknown = set(changes) - EDITABLE_LINE_FIELDS
        if unknown:
            raise ValueError(f"Not editable on a purchase order line: {sorted(unknown)}")

        if "quantity_ordered" in changes:
            PurchaseOrderLineValidator.check_quantity_floor(
                line=line, new_quantity_ordered=changes["quantity_ordered"]
            )
            cls._resolve_quantity_shortfall(
                line=line,
                new_quantity_ordered=changes["quantity_ordered"],
                actor=actor,
                commit=commit,
            )

        purchase_order = line.purchase_order
        PurchaseOrderNarrator.post_with_snapshot(
            purchase_order=purchase_order,
            message=PurchaseOrderNarrator.line_edited(line_number=line.line_number),
            row=line,
            actor=actor,
        )

        for field, value in changes.items():
            setattr(line, field, value)
        line.updated_by = actor
        line.save()

        PurchaseOrderCostManager.recompute(
            purchase_order=purchase_order, actor=actor, commit=commit
        )
        return line

    @classmethod
    def _resolve_quantity_shortfall(
        cls, *, line: PurchaseOrderLine, new_quantity_ordered: Decimal, actor=None, commit: bool = True
    ) -> None:
        """reallocation_resolution_portal.md §5: classify the shortfall shape
        against this line's active demand claims before the new quantity is
        saved. `check_quantity_floor` has already refused anything that would
        cut below the LOCKED total, so every path here is a valid outcome.

          - still covers every active claim -> nothing to do.
          - exactly one active, unlocked claim, short -> silently resolved to
            the new quantity (§7.9's one-to-one shortcut — there is exactly
            one place the number can go).
          - 2+ claims short, or the sole claim locked -> raises
            ReallocationRequired so the caller can open the Reallocation
            Portal instead of a flat refusal (§5's flowchart).
        """
        claims = list(
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line=line, is_active=True, deleted_at__isnull=True
            ).select_related("part_demand")
        )
        total_claimed = sum((c.quantity_allocated for c in claims), Decimal("0"))
        if new_quantity_ordered >= total_claimed:
            return

        locked = [c for c in claims if c.is_locked]

        if len(claims) == 1 and not locked:
            claim = claims[0]
            old_quantity = claim.quantity_allocated
            claim.quantity_allocated = new_quantity_ordered
            claim.updated_by = actor
            claim.save(update_fields=["quantity_allocated", "updated_by", "updated_at"])

            PurchaseOrderDemandLinkManager.requeue_if_short(
                demand=claim.part_demand, actor=actor, commit=commit
            )
            PurchaseOrderNarrator.post(
                purchase_order=line.purchase_order,
                message=PurchaseOrderNarrator.claim_auto_updated_by_shortfall(
                    demand_id=claim.part_demand_id,
                    line_number=line.line_number,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity_ordered,
                ),
                actor=actor,
            )
            return

        locked_total = sum((c.quantity_allocated for c in locked), Decimal("0"))
        raise ReallocationRequired(
            line_id=line.pk,
            new_quantity_ordered=new_quantity_ordered,
            total_claimed=total_claimed,
            locked_total=locked_total,
            claim_count=len(claims),
        )

    @classmethod
    def cancel_line(
        cls, *, line: PurchaseOrderLine, actor=None, commit: bool = True
    ) -> int:
        """Soft-delete the line, remove its demand links, and reset those
        demands' purchasing_state (D56).

        There is no line status column and no is_cancelled flag (D57): a
        cancelled line is a soft-deleted line whose Event comment explains it.
        Because the one-line-per-part rule is scoped to ACTIVE lines, a
        cancel-then-replace does not trip the guard — which is the honest
        record of a substitution or re-price.
        """
        purchase_order = line.purchase_order

        released = PurchaseOrderDemandLinkManager.remove_for_line(
            line=line, actor=actor, commit=commit
        )

        PurchaseOrderNarrator.post_with_snapshot(
            purchase_order=purchase_order,
            message=PurchaseOrderNarrator.line_cancelled(
                line_number=line.line_number, released_demand_count=released
            ),
            row=line,
            actor=actor,
        )

        line.deleted_at = timezone.now()
        line.updated_by = actor
        line.save(update_fields=["deleted_at", "updated_by", "updated_at"])

        PurchaseOrderCostManager.recompute(
            purchase_order=purchase_order, actor=actor, commit=commit
        )
        return released

    @classmethod
    def reorder(
        cls, *, purchase_order, ordered_line_ids: list[int], actor=None
    ) -> None:
        """Renumber lines to the given order.

        Two passes with an offset, because (purchase_order, line_number) is
        unique and a single pass would collide mid-renumber.
        """
        offset = (
            purchase_order.lines.aggregate(top=Max("line_number"))["top"] or 0
        ) + 1000
        lines = {
            line.pk: line
            for line in purchase_order.lines.filter(pk__in=ordered_line_ids)
        }

        for index, line_id in enumerate(ordered_line_ids):
            line = lines.get(line_id)
            if line is None:
                continue
            line.line_number = offset + index
            line.updated_by = actor
            line.save(update_fields=["line_number", "updated_by", "updated_at"])

        for index, line_id in enumerate(ordered_line_ids, start=1):
            line = lines.get(line_id)
            if line is None:
                continue
            line.line_number = index
            line.save(update_fields=["line_number", "updated_at"])
