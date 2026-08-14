"""Adaptor: the wizard's session-backed draft.

THE DRAFT IS NOT A DATABASE ROW. It is a plain structure that lives in the
session and accumulates across many requests, committing once, atomically, at
the end. A half-built PO in the database would be visible to other Buyers,
would need a status value meaning "not really a PO yet", and would leave
orphans when abandoned.

The route shape is the front-end kit's problem; what matters here is that the
control layer supports accumulation across requests without writing anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

from app.procurement.control_layer.errors import ProcurementValidationError

#: Session key the wizard stores its draft under.
DRAFT_SESSION_KEY = "procurement_purchase_order_draft"


@dataclass
class DraftAllocation:
    demand_id: int
    quantity_allocated: Decimal
    # D42's opt-out: False leaves the demand unapproved, preserving the strict
    # approve-first process for that item.
    auto_approve: bool = True
    # D28's explicit choice: the Buyer elected to raise the demand's request
    # rather than leave the excess unallocated.
    raise_request: bool = False


@dataclass
class DraftLine:
    part_id: int
    quantity_ordered: Decimal
    unit_cost: Decimal
    expected_delivery_date: object = None
    notes: str = ""
    # D85/D88 — provenance the price chip's "Use this" or the picker stamped.
    # Blank when the Buyer just typed a number themselves.
    unit_cost_source: str = ""
    unit_cost_confidence: str = ""
    unit_cost_asserted_at: object = None
    allocations: list[DraftAllocation] = field(default_factory=list)


@dataclass
class PurchaseOrderDraft:
    vendor_id: int
    domain_id: int
    vendor_contact: str = ""
    order_date: object = None
    expected_delivery_date: object = None
    shipping_cost: Decimal | None = None
    tax_amount: Decimal | None = None
    other_amount: Decimal | None = None
    notes: str = ""
    lines: list[DraftLine] = field(default_factory=list)

    def to_session(self) -> dict:
        return {
            "vendor_id": self.vendor_id,
            "domain_id": self.domain_id,
            "vendor_contact": self.vendor_contact,
            "order_date": str(self.order_date) if self.order_date else None,
            "expected_delivery_date": (
                str(self.expected_delivery_date)
                if self.expected_delivery_date
                else None
            ),
            "shipping_cost": str(self.shipping_cost) if self.shipping_cost else None,
            "tax_amount": str(self.tax_amount) if self.tax_amount else None,
            "other_amount": str(self.other_amount) if self.other_amount else None,
            "notes": self.notes,
            "lines": [
                {
                    "part_id": line.part_id,
                    "quantity_ordered": str(line.quantity_ordered),
                    "unit_cost": str(line.unit_cost),
                    "expected_delivery_date": (
                        str(line.expected_delivery_date)
                        if line.expected_delivery_date
                        else None
                    ),
                    "notes": line.notes,
                    "unit_cost_source": line.unit_cost_source,
                    "unit_cost_confidence": line.unit_cost_confidence,
                    "unit_cost_asserted_at": (
                        str(line.unit_cost_asserted_at) if line.unit_cost_asserted_at else None
                    ),
                    "allocations": [
                        {
                            "demand_id": a.demand_id,
                            "quantity_allocated": str(a.quantity_allocated),
                            "auto_approve": a.auto_approve,
                            "raise_request": a.raise_request,
                        }
                        for a in line.allocations
                    ],
                }
                for line in self.lines
            ],
        }


class PurchaseOrderDraftAdaptor:
    @classmethod
    def from_session(cls, session) -> PurchaseOrderDraft | None:
        raw = session.get(DRAFT_SESSION_KEY)
        if not raw:
            return None
        return cls.from_dict(raw)

    @classmethod
    def save_to_session(cls, session, draft: PurchaseOrderDraft) -> None:
        session[DRAFT_SESSION_KEY] = draft.to_session()
        session.modified = True

    @classmethod
    def clear_session(cls, session) -> None:
        session.pop(DRAFT_SESSION_KEY, None)
        session.modified = True

    @classmethod
    def from_dict(cls, raw: dict) -> PurchaseOrderDraft:
        errors: list[str] = []

        vendor_id = cls._int(raw.get("vendor_id"))
        if not vendor_id:
            errors.append("A vendor is required.")
        domain_id = cls._int(raw.get("domain_id"))
        if not domain_id:
            errors.append("A domain is required.")

        lines: list[DraftLine] = []
        for index, raw_line in enumerate(raw.get("lines") or [], start=1):
            part_id = cls._int(raw_line.get("part_id"))
            if not part_id:
                errors.append(f"Line {index}: a part is required.")
            quantity = cls._decimal(raw_line.get("quantity_ordered"))
            if quantity is None or quantity <= 0:
                errors.append(f"Line {index}: ordered quantity must be positive.")
            unit_cost = cls._decimal(raw_line.get("unit_cost"))
            if unit_cost is None or unit_cost < 0:
                errors.append(f"Line {index}: unit cost cannot be negative.")

            allocations: list[DraftAllocation] = []
            for raw_alloc in raw_line.get("allocations") or []:
                demand_id = cls._int(raw_alloc.get("demand_id"))
                allocated = cls._decimal(raw_alloc.get("quantity_allocated"))
                if not demand_id or allocated is None or allocated <= 0:
                    errors.append(
                        f"Line {index}: each allocation needs a demand and a "
                        f"positive quantity."
                    )
                    continue
                allocations.append(
                    DraftAllocation(
                        demand_id=demand_id,
                        quantity_allocated=allocated,
                        auto_approve=bool(raw_alloc.get("auto_approve", True)),
                        raise_request=bool(raw_alloc.get("raise_request", False)),
                    )
                )

            if part_id and quantity is not None and unit_cost is not None:
                lines.append(
                    DraftLine(
                        part_id=part_id,
                        quantity_ordered=quantity,
                        unit_cost=unit_cost,
                        expected_delivery_date=cls._date(
                            raw_line.get("expected_delivery_date")
                        ),
                        notes=(raw_line.get("notes") or "").strip(),
                        unit_cost_source=(raw_line.get("unit_cost_source") or "").strip(),
                        unit_cost_confidence=(raw_line.get("unit_cost_confidence") or "").strip(),
                        unit_cost_asserted_at=cls._date(raw_line.get("unit_cost_asserted_at")),
                        allocations=allocations,
                    )
                )

        if errors:
            raise ProcurementValidationError(errors)

        return PurchaseOrderDraft(
            vendor_id=vendor_id,
            domain_id=domain_id,
            vendor_contact=(raw.get("vendor_contact") or "").strip(),
            order_date=cls._date(raw.get("order_date")),
            expected_delivery_date=cls._date(raw.get("expected_delivery_date")),
            shipping_cost=cls._decimal(raw.get("shipping_cost")),
            tax_amount=cls._decimal(raw.get("tax_amount")),
            other_amount=cls._decimal(raw.get("other_amount")),
            notes=(raw.get("notes") or "").strip(),
            lines=lines,
        )

    # ------------------------------------------------------------------ #

    @staticmethod
    def _int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decimal(value) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _date(value):
        if not value:
            return None
        return parse_date(str(value))
