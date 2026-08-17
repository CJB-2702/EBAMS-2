"""Struct: the Reallocation Portal's full resolution state for one PO line
(reallocation_resolution_portal.md §4 point 2, §5).

Re-derived from live DB state on every load, never from the session draft
(§10 point 3 — no cached total). The session draft (reallocation_draft.py)
only carries the Buyer's in-progress proposed values; this struct is what a
render call joins those proposed values against.

THREE claim categories, kept structurally distinct per §4's comparison table:
  open      — this line's active, unlocked claims. Adjustable here.
  locked    — this line's active, LOCKED claims (arrived/received). Adjustable
              only through the two-popup unlock sequence.
  external  — claims the affected demands hold on OTHER orders. Read-only,
              never counted in this line's own sum(OPEN + LOCKED) math, and
              never mistaken for the arrived/received lock above.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.procurement.control_layer.domain_structs.demand_external_claims_struct import (
    DemandExternalClaimsStruct,
    ExternalClaim,
)
from app.procurement.models import PurchaseOrderDemandLink, PurchaseOrderLine


@dataclass(frozen=True)
class ReallocationClaim:
    link_id: int
    demand_id: int
    quantity_allocated: Decimal
    priority: str
    needed_by: object
    demand_created_at: object
    external_claims: tuple[ExternalClaim, ...] = ()


@dataclass(frozen=True)
class ReallocationPortalStruct:
    line_id: int
    line_number: int
    purchase_order_id: int
    po_number: str
    open_claims: tuple[ReallocationClaim, ...] = ()
    locked_claims: tuple[ReallocationClaim, ...] = ()

    @property
    def open_total(self) -> Decimal:
        return sum((c.quantity_allocated for c in self.open_claims), Decimal("0"))

    @property
    def locked_total(self) -> Decimal:
        return sum((c.quantity_allocated for c in self.locked_claims), Decimal("0"))

    @classmethod
    def load(cls, *, line_id: int) -> "ReallocationPortalStruct":
        line = PurchaseOrderLine.objects.select_related("purchase_order").get(pk=line_id)
        links = list(
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line=line, is_active=True, deleted_at__isnull=True
            ).select_related("part_demand")
        )
        external_by_demand = DemandExternalClaimsStruct.load_many(
            demand_ids={link.part_demand_id for link in links},
            exclude_purchase_order_id=line.purchase_order_id,
        )

        def _claim(link: PurchaseOrderDemandLink) -> ReallocationClaim:
            demand = link.part_demand
            return ReallocationClaim(
                link_id=link.pk,
                demand_id=demand.pk,
                quantity_allocated=link.quantity_allocated,
                priority=demand.priority,
                needed_by=demand.needed_by,
                demand_created_at=demand.created_at,
                external_claims=external_by_demand.get(
                    demand.pk, DemandExternalClaimsStruct(demand_id=demand.pk)
                ).claims,
            )

        open_claims = tuple(_claim(link) for link in links if not link.is_locked)
        locked_claims = tuple(_claim(link) for link in links if link.is_locked)

        return cls(
            line_id=line.pk,
            line_number=line.line_number,
            purchase_order_id=line.purchase_order_id,
            po_number=line.purchase_order.po_number,
            open_claims=open_claims,
            locked_claims=locked_claims,
        )

    def to_dict(self) -> dict:
        def _c(claim: ReallocationClaim) -> dict:
            return {
                "link_id": claim.link_id,
                "demand_id": claim.demand_id,
                "quantity_allocated": claim.quantity_allocated,
                "priority": claim.priority,
                "needed_by": claim.needed_by,
                "external_claims": [
                    {
                        "link_id": e.link_id,
                        "purchase_order_id": e.purchase_order_id,
                        "po_number": e.po_number,
                        "line_id": e.line_id,
                        "line_number": e.line_number,
                        "quantity_allocated": e.quantity_allocated,
                        "is_locked": e.is_locked,
                    }
                    for e in claim.external_claims
                ],
            }

        return {
            "line_id": self.line_id,
            "line_number": self.line_number,
            "purchase_order_id": self.purchase_order_id,
            "po_number": self.po_number,
            "open_claims": [_c(c) for c in self.open_claims],
            "locked_claims": [_c(c) for c in self.locked_claims],
            "open_total": self.open_total,
            "locked_total": self.locked_total,
        }
