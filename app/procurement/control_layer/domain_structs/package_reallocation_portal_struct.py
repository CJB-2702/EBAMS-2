"""Struct: read-model for the Package↔PO Domain's Reallocation Portal
(reallocation_resolution_portal.md §3, §5 — Phase 5's UI-facing counterpart
to `PackageReallocationWaterfallHandler`/`PackageReallocationValidator`).

Deliberately simpler than the Demand↔PO Domain's `ReallocationPortalStruct`:
a package line has no "external claims" concept (§3 — its only ceiling is its
own shipped quantity, and every claim against it is already local to that one
line). This struct carries no `external_claims` field, on purpose — do not
add one back in by analogy with the other domain.

No import from, or reuse of, the Demand↔PO Domain's struct or any of its
helpers (§7.7 — the two domains never share state or code). This is an
independent, parallel implementation of the same shape.

Re-derived from live DB state on every load, never from the session draft —
`package_reallocation_draft.py` only carries the Receiver's in-progress
proposed values; this struct is what a render call joins those proposed
values against (§10 point 3 — no cached total).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.procurement.models import PurchaseOrderShipmentLink, ShipmentLine


@dataclass(frozen=True)
class PackageReallocationClaim:
    link_id: int
    purchase_order_id: int
    po_number: str
    line_id: int
    line_number: int
    quantity_allocated: Decimal


@dataclass(frozen=True)
class PackageReallocationPortalStruct:
    shipment_line_id: int
    part_number: str
    quantity: Decimal
    open_claims: tuple[PackageReallocationClaim, ...] = ()
    locked_claims: tuple[PackageReallocationClaim, ...] = ()

    @property
    def open_total(self) -> Decimal:
        return sum((c.quantity_allocated for c in self.open_claims), Decimal("0"))

    @property
    def locked_total(self) -> Decimal:
        return sum((c.quantity_allocated for c in self.locked_claims), Decimal("0"))

    @classmethod
    def load(cls, *, shipment_line_id: int) -> "PackageReallocationPortalStruct":
        line = ShipmentLine.objects.select_related("part").get(pk=shipment_line_id)
        links = list(
            PurchaseOrderShipmentLink.objects.filter(
                shipment_line=line, deleted_at__isnull=True
            ).select_related("purchase_order_line__purchase_order")
        )

        def _claim(link: PurchaseOrderShipmentLink) -> PackageReallocationClaim:
            po_line = link.purchase_order_line
            return PackageReallocationClaim(
                link_id=link.pk,
                purchase_order_id=po_line.purchase_order_id,
                po_number=po_line.purchase_order.po_number,
                line_id=po_line.pk,
                line_number=po_line.line_number,
                quantity_allocated=link.quantity_allocated,
            )

        open_claims = tuple(_claim(link) for link in links if not link.is_locked)
        locked_claims = tuple(_claim(link) for link in links if link.is_locked)

        return cls(
            shipment_line_id=line.pk,
            part_number=line.part.part_number,
            quantity=line.quantity,
            open_claims=open_claims,
            locked_claims=locked_claims,
        )

    def to_dict(self) -> dict:
        def _c(claim: PackageReallocationClaim) -> dict:
            return {
                "link_id": claim.link_id,
                "purchase_order_id": claim.purchase_order_id,
                "po_number": claim.po_number,
                "line_id": claim.line_id,
                "line_number": claim.line_number,
                "quantity_allocated": claim.quantity_allocated,
            }

        return {
            "shipment_line_id": self.shipment_line_id,
            "part_number": self.part_number,
            "quantity": self.quantity,
            "open_claims": [_c(c) for c in self.open_claims],
            "locked_claims": [_c(c) for c in self.locked_claims],
            "open_total": self.open_total,
            "locked_total": self.locked_total,
        }
