"""Search: the Buyer's purchase-order queue — filters and the linkage badge.

D67 IS THE WHOLE DESIGN CONSTRAINT HERE. A PO reaches its allocations through
two joins (PurchaseOrder -> lines -> allocations), so annotating `Sum` over both
in the same query multiplies every ordered quantity by that line's allocation
count. Both rollups below are therefore CORRELATED SUBQUERIES that aggregate in
their own scope and hand back one scalar each. Never replace either with a
`Sum("lines__…")` beside the other.

The linkage badge exists so the results table does not issue a per-row query for
"is this PO fully linked" — the same mistake the legacy list made.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import (
    DecimalField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
)
from django.db.models.functions import Coalesce

from app.procurement.models import (
    PurchaseOrder,
    PurchaseOrderDemandLink,
    PurchaseOrderLine,
)

_DECIMAL = DecimalField(max_digits=14, decimal_places=3)

LINKAGE_NONE = "unlinked"
LINKAGE_PARTIAL = "partially_linked"
LINKAGE_FULL = "fully_linked"

LINKAGE_LABELS = {
    LINKAGE_NONE: "Unlinked",
    LINKAGE_PARTIAL: "Partially linked",
    LINKAGE_FULL: "Fully linked",
}

LINKAGE_TAG_CLASSES = {
    LINKAGE_NONE: "is-light",
    LINKAGE_PARTIAL: "is-warning",
    LINKAGE_FULL: "is-success",
}


def _ordered_subquery():
    return Subquery(
        PurchaseOrderLine.objects.filter(
            purchase_order=OuterRef("pk"), deleted_at__isnull=True
        )
        .values("purchase_order")
        .annotate(total=Sum("quantity_ordered"))
        .values("total")[:1],
        output_field=_DECIMAL,
    )


def _allocated_subquery():
    return Subquery(
        PurchaseOrderDemandLink.objects.filter(
            purchase_order_line__purchase_order=OuterRef("pk"),
            is_active=True,
            deleted_at__isnull=True,
        )
        .values("purchase_order_line__purchase_order")
        .annotate(total=Sum("quantity_allocated"))
        .values("total")[:1],
        output_field=_DECIMAL,
    )


class PurchaseOrderSearch:
    @classmethod
    def filter(
        cls,
        *,
        domain_ids,
        q: str = "",
        status: str = "",
        approval_state: str = "",
        vendor_id: int | None = None,
        domain_id: int | None = None,
        part_id: int | None = None,
        date_from=None,
        date_to=None,
    ) -> QuerySet[PurchaseOrder]:
        """The index page's one read. `domain_ids` is the D5 fence and is
        required — passing None would silently unfence the list, so the caller
        must hand over the user's domains even when that list is empty."""
        qs = (
            PurchaseOrder.objects.filter(
                domain_id__in=domain_ids, deleted_at__isnull=True
            )
            .select_related("vendor", "domain")
            .annotate(
                ordered_total=Coalesce(
                    _ordered_subquery(), Decimal("0"), output_field=_DECIMAL
                ),
                allocated_total=Coalesce(
                    _allocated_subquery(), Decimal("0"), output_field=_DECIMAL
                ),
            )
        )

        if q:
            text_match = (
                Q(po_number__icontains=q)
                | Q(vendor__name__icontains=q)
                | Q(vendor_contact__icontains=q)
            )
            # The buyer-entered vendor number is a first-class search key — it
            # is the string the vendor says on the phone. Phase 0 adds it.
            if _has_vendor_po_id():
                text_match |= Q(vendor_po_id__icontains=q)
            qs = qs.filter(text_match)
        if status:
            qs = qs.filter(status=status)
        if approval_state and _has_approval_state():
            qs = qs.filter(approval_state=approval_state)
        if vendor_id:
            qs = qs.filter(vendor_id=vendor_id)
        if domain_id:
            qs = qs.filter(domain_id=domain_id)
        if part_id:
            qs = qs.filter(
                lines__part_id=part_id, lines__deleted_at__isnull=True
            ).distinct()
        if date_from:
            qs = qs.filter(order_date__gte=date_from)
        if date_to:
            qs = qs.filter(order_date__lte=date_to)

        return qs.order_by("-order_date", "-created_at")

    @staticmethod
    def linkage_of(purchase_order) -> str:
        """Read off the annotations above — never a per-row query.

        A PO with no lines at all reads as unlinked rather than "fully linked by
        vacuous truth", which is what a bare `allocated >= ordered` would say.
        """
        ordered = purchase_order.ordered_total or Decimal("0")
        allocated = purchase_order.allocated_total or Decimal("0")
        if allocated <= 0:
            return LINKAGE_NONE
        if ordered > 0 and allocated >= ordered:
            return LINKAGE_FULL
        return LINKAGE_PARTIAL

    @classmethod
    def annotate_display(cls, purchase_orders) -> list:
        """Attach the badge to each row once, in Python, off annotations already
        in hand. Evaluates the queryset — callers paginate before calling."""
        rows = list(purchase_orders)
        for po in rows:
            linkage = cls.linkage_of(po)
            po.linkage_status = linkage
            po.linkage_label = LINKAGE_LABELS[linkage]
            po.linkage_tag_class = LINKAGE_TAG_CLASSES[linkage]
        return rows

def _has_approval_state() -> bool:
    """Phase 0 adds the column; until then its filters are no-ops."""
    return _has_field("approval_state")


def _has_vendor_po_id() -> bool:
    return _has_field("vendor_po_id")


def _has_field(name: str) -> bool:
    return any(f.name == name for f in PurchaseOrder._meta.get_fields())
