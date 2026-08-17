"""Struct: the assembled PO — header, lines, allocations, and every derived
total, in ONE annotated query.

The legacy get_po_lines_with_demands built this by looping lines, constructing
a context per line, and issuing several queries inside each — then resolving
each demand's origin on top. A 40-line PO cost well over a hundred queries.
Annotate once (D53).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Prefetch, Q, Sum
from django.db.models.functions import Coalesce

from app.procurement.control_layer.domain_structs.demand_external_claims_struct import (
    DemandExternalClaimsStruct,
    ExternalClaim,
)
from app.procurement.control_layer.domain_structs.purchase_order_line_struct import (
    PurchaseOrderLineStruct,
)
from app.procurement.models import (
    PurchaseOrder,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)


@dataclass(frozen=True)
class AllocationSlice:
    link_id: int
    demand_id: int
    quantity_allocated: Decimal
    is_active: bool
    demand_state: str
    purchasing_state: str
    # Reallocation Resolution decision (supersedes D55) — see
    # PurchaseOrderDemandLink's docstring.
    quantity_received: Decimal = Decimal("0")
    is_locked: bool = False
    # §4, point 1: this demand's active claims on OTHER orders, read-only
    # here — never editable from this screen (§7.10).
    external_claims: tuple[ExternalClaim, ...] = ()


@dataclass(frozen=True)
class PurchaseOrderStruct:
    purchase_order_id: int
    po_number: str
    vendor_id: int
    vendor_name: str
    vendor_contact: str
    domain_id: int
    status: str
    order_date: object
    expected_delivery_date: object
    shipping_cost: Decimal | None
    tax_amount: Decimal | None
    other_amount: Decimal | None
    total_cost: Decimal | None
    notes: str
    event_id: int | None

    lines: tuple[PurchaseOrderLineStruct, ...] = ()
    allocations_by_line: dict[int, tuple[AllocationSlice, ...]] = None

    @classmethod
    def load(cls, *, purchase_order_id: int) -> "PurchaseOrderStruct":
        annotated_lines = (
            PurchaseOrderLine.objects.filter(deleted_at__isnull=True)
            .select_related("part")
            .annotate(
                allocated_total=Coalesce(
                    Sum(
                        "allocations__quantity_allocated",
                        filter=Q(
                            allocations__is_active=True,
                            allocations__deleted_at__isnull=True,
                        ),
                    ),
                    Decimal("0"),
                    output_field=_DECIMAL,
                ),
                active_allocations=Count(
                    "allocations",
                    filter=Q(
                        allocations__is_active=True,
                        allocations__deleted_at__isnull=True,
                    ),
                    distinct=True,
                ),
            )
            .order_by("line_number")
        )

        po = (
            PurchaseOrder.objects.select_related("vendor")
            .prefetch_related(
                Prefetch("lines", queryset=annotated_lines, to_attr="annotated_lines"),
            )
            .get(pk=purchase_order_id)
        )

        line_structs = tuple(
            PurchaseOrderLineStruct(
                line_id=line.pk,
                line_number=line.line_number,
                part_id=line.part_id,
                part_number=line.part.part_number,
                part_name=line.part.name,
                quantity_ordered=line.quantity_ordered,
                unit_cost=line.unit_cost,
                expected_delivery_date=line.expected_delivery_date,
                notes=line.notes,
                line_total=line.quantity_ordered * line.unit_cost,
                quantity_allocated_total=line.allocated_total,
                quantity_unallocated=line.quantity_ordered - line.allocated_total,
                active_allocation_count=line.active_allocations,
            )
            for line in po.annotated_lines
        )

        allocations: dict[int, list[AllocationSlice]] = {}
        link_rows = (
            PurchaseOrderDemandLink.objects.filter(
                purchase_order_line__purchase_order=po,
                deleted_at__isnull=True,
            )
            .select_related("part_demand")
            .annotate(line_id=F("purchase_order_line_id"))
        )
        # One query for every demand's external claims on this page, rather
        # than one per row (§4, point 1).
        external_by_demand = DemandExternalClaimsStruct.load_many(
            demand_ids={link.part_demand_id for link in link_rows},
            exclude_purchase_order_id=po.pk,
        )
        for link in link_rows:
            allocations.setdefault(link.purchase_order_line_id, []).append(
                AllocationSlice(
                    link_id=link.pk,
                    demand_id=link.part_demand_id,
                    quantity_allocated=link.quantity_allocated,
                    is_active=link.is_active,
                    demand_state=link.part_demand.demand_state,
                    purchasing_state=link.part_demand.purchasing_state,
                    quantity_received=link.quantity_received,
                    is_locked=link.is_locked,
                    external_claims=external_by_demand.get(
                        link.part_demand_id,
                        DemandExternalClaimsStruct(demand_id=link.part_demand_id),
                    ).claims,
                )
            )

        return cls(
            purchase_order_id=po.pk,
            po_number=po.po_number,
            vendor_id=po.vendor_id,
            vendor_name=po.vendor.name,
            vendor_contact=po.vendor_contact,
            domain_id=po.domain_id,
            status=po.status,
            order_date=po.order_date,
            expected_delivery_date=po.expected_delivery_date,
            shipping_cost=po.shipping_cost,
            tax_amount=po.tax_amount,
            other_amount=po.other_amount,
            total_cost=po.total_cost,
            notes=po.notes,
            event_id=po.event_id,
            lines=line_structs,
            allocations_by_line={
                key: tuple(value) for key, value in allocations.items()
            },
        )

    def to_dict(self) -> dict:
        return {
            "purchase_order_id": self.purchase_order_id,
            "po_number": self.po_number,
            "vendor_id": self.vendor_id,
            "vendor_name": self.vendor_name,
            "vendor_contact": self.vendor_contact,
            "domain_id": self.domain_id,
            "status": self.status,
            "order_date": self.order_date,
            "expected_delivery_date": self.expected_delivery_date,
            "shipping_cost": self.shipping_cost,
            "tax_amount": self.tax_amount,
            "other_amount": self.other_amount,
            "total_cost": self.total_cost,
            "notes": self.notes,
            "event_id": self.event_id,
            "lines": [line.to_dict() for line in self.lines],
            "allocations_by_line": {
                line_id: [
                    {
                        "link_id": a.link_id,
                        "demand_id": a.demand_id,
                        "quantity_allocated": a.quantity_allocated,
                        "is_active": a.is_active,
                        "demand_state": a.demand_state,
                        "purchasing_state": a.purchasing_state,
                        "quantity_received": a.quantity_received,
                        "is_locked": a.is_locked,
                        "external_claims": [
                            {
                                "link_id": c.link_id,
                                "purchase_order_id": c.purchase_order_id,
                                "po_number": c.po_number,
                                "line_id": c.line_id,
                                "line_number": c.line_number,
                                "quantity_allocated": c.quantity_allocated,
                                "is_locked": c.is_locked,
                            }
                            for c in a.external_claims
                        ],
                    }
                    for a in slices
                ]
                for line_id, slices in (self.allocations_by_line or {}).items()
            },
        }
