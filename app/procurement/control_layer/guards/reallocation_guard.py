"""Guard type: Validator. The Reallocation Portal's manual-entry cap and
commit gate (reallocation_resolution_portal.md §5, §6, §7.4, §7.5).

THE CEILING IS ABSOLUTE (§7.5): under-claiming is a normal, permitted outcome
(§7.4) — a Buyer may leave part of the source unclaimed, and it returns to the
open pool. Over-claiming, through either the auto-allocate or manual path, is
never allowed. The commit gate mirrors the source document's flowchart
exactly: `sum(OPEN + LOCKED) <= new_source_qty`, not `==` — a resolution that
leaves some of the source unclaimed is a valid, complete resolution.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError


class ReallocationValidator:
    @classmethod
    def check_manual_entry(
        cls,
        *,
        values: dict[int, Decimal],
        locked_total: Decimal,
        new_source_qty: Decimal,
    ) -> None:
        errors: list[str] = []
        for link_id, value in values.items():
            if value is None or value < 0:
                errors.append(f"Claim #{link_id}'s value cannot be negative.")
        if errors:
            raise ProcurementValidationError(errors)

        open_total = sum(values.values(), Decimal("0"))
        if open_total + locked_total > new_source_qty:
            raise ProcurementValidationError(
                [
                    f"{open_total} entered across open claims plus {locked_total} "
                    f"already locked comes to more than the new quantity of "
                    f"{new_source_qty}. Reduce one or more values — leaving some "
                    f"unclaimed is allowed, exceeding the source is not."
                ]
            )

    @classmethod
    def check_commit_ready(
        cls, *, open_total: Decimal, locked_total: Decimal, new_source_qty: Decimal
    ) -> None:
        if open_total + locked_total > new_source_qty:
            raise ProcurementValidationError(
                [
                    f"Claims still total {open_total + locked_total} against a "
                    f"source of {new_source_qty}. Resolve the remaining "
                    f"{open_total + locked_total - new_source_qty} before this "
                    f"can be saved."
                ]
            )
