"""Struct: a demand's active claims on orders OTHER than the one currently on
screen (reallocation_resolution_portal.md §4).

ONE STRUCT, TWO CALL SITES — the linkage screen's current-links list and the
Reallocation Portal's external-claims display both read this, so the query
cannot drift between them. Every claim it returns is READ-ONLY here: neither
call site may edit, unlock, or otherwise act on an "external" claim — that
authority exists in exactly one place, the other order's own linkage screen
(§7.10). This is a different lock category from Phase 1/2's arrived/received
LOCKED state and must never be merged with it (§4's comparison table) — an
external claim can be perfectly OPEN on its own order and still shows up here,
locked or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.procurement.models import PurchaseOrderDemandLink


@dataclass(frozen=True)
class ExternalClaim:
    link_id: int
    purchase_order_id: int
    po_number: str
    line_id: int
    line_number: int
    quantity_allocated: Decimal
    is_locked: bool


@dataclass(frozen=True)
class DemandExternalClaimsStruct:
    demand_id: int
    claims: tuple[ExternalClaim, ...] = ()

    @classmethod
    def load(
        cls, *, demand_id: int, exclude_purchase_order_id: int | None = None
    ) -> "DemandExternalClaimsStruct":
        qs = PurchaseOrderDemandLink.objects.filter(
            part_demand_id=demand_id, is_active=True, deleted_at__isnull=True
        ).select_related("purchase_order_line__purchase_order")
        if exclude_purchase_order_id is not None:
            qs = qs.exclude(
                purchase_order_line__purchase_order_id=exclude_purchase_order_id
            )

        claims = tuple(
            ExternalClaim(
                link_id=link.pk,
                purchase_order_id=link.purchase_order_line.purchase_order_id,
                po_number=link.purchase_order_line.purchase_order.po_number,
                line_id=link.purchase_order_line_id,
                line_number=link.purchase_order_line.line_number,
                quantity_allocated=link.quantity_allocated,
                is_locked=link.is_locked,
            )
            for link in qs
        )
        return cls(demand_id=demand_id, claims=claims)

    @classmethod
    def load_many(
        cls, *, demand_ids, exclude_purchase_order_id: int | None = None
    ) -> dict[int, "DemandExternalClaimsStruct"]:
        """The linkage screen's own call site: one query for every demand on
        the page rather than one per row. `exclude_purchase_order_id` is the
        PO the screen is already showing — a claim on a DIFFERENT LINE of
        that same order is not "external" (§4/§7.10 draw the line at ORDER,
        not line); only a claim belonging to a different order entirely
        counts."""
        qs = PurchaseOrderDemandLink.objects.filter(
            part_demand_id__in=demand_ids, is_active=True, deleted_at__isnull=True
        ).select_related("purchase_order_line__purchase_order")
        if exclude_purchase_order_id is not None:
            qs = qs.exclude(
                purchase_order_line__purchase_order_id=exclude_purchase_order_id
            )

        by_demand: dict[int, list[ExternalClaim]] = {}
        for link in qs:
            by_demand.setdefault(link.part_demand_id, []).append(
                ExternalClaim(
                    link_id=link.pk,
                    purchase_order_id=link.purchase_order_line.purchase_order_id,
                    po_number=link.purchase_order_line.purchase_order.po_number,
                    line_id=link.purchase_order_line_id,
                    line_number=link.purchase_order_line.line_number,
                    quantity_allocated=link.quantity_allocated,
                    is_locked=link.is_locked,
                )
            )
        return {
            demand_id: cls(demand_id=demand_id, claims=tuple(claims))
            for demand_id, claims in by_demand.items()
        }

    def to_dict(self) -> dict:
        return {
            "demand_id": self.demand_id,
            "claims": [
                {
                    "link_id": c.link_id,
                    "purchase_order_id": c.purchase_order_id,
                    "po_number": c.po_number,
                    "line_id": c.line_id,
                    "line_number": c.line_number,
                    "quantity_allocated": c.quantity_allocated,
                    "is_locked": c.is_locked,
                }
                for c in self.claims
            ],
        }
