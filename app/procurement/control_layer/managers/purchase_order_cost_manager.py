"""The only writer of PurchaseOrder.total_cost.

Denormalized for the same reason purchased_qty is: a PO list should not sum
lines per row. Recomputed on every line write, never set by a caller.
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, F, Sum
from django.db.models.functions import Coalesce


class PurchaseOrderCostManager:
    @classmethod
    def recompute(cls, *, purchase_order, actor=None, commit: bool = True) -> Decimal:
        """total_cost = sum(line totals) + shipping + tax + other.

        Line totals are annotated in one query rather than summed in Python
        over @property calls (D53) — the legacy model's line_total property
        issued a query per line on access.
        """
        line_total = purchase_order.lines.filter(deleted_at__isnull=True).aggregate(
            total=Coalesce(
                Sum(
                    F("quantity_ordered") * F("unit_cost"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                Decimal("0"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )["total"]

        total = (
            line_total
            + (purchase_order.shipping_cost or Decimal("0"))
            + (purchase_order.tax_amount or Decimal("0"))
            + (purchase_order.other_amount or Decimal("0"))
        )

        purchase_order.total_cost = total
        purchase_order.updated_by = actor
        if commit:
            purchase_order.save(
                update_fields=["total_cost", "updated_by", "updated_at"]
            )
        return total
