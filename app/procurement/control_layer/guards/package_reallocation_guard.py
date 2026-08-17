"""Guard type: Validator. The Package Reallocation Portal's manual-entry cap
and commit gate — Phase 5's independent mirror of ReallocationValidator
(Demand↔PO Domain). Deliberately a separate class in a separate file: the two
domains never share state (build_plan.md's guardrail), only the shape of the
rule.
"""

from __future__ import annotations

from decimal import Decimal

from app.procurement.control_layer.errors import ProcurementValidationError


class PackageReallocationValidator:
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
                    f"already locked comes to more than the new shipped quantity "
                    f"of {new_source_qty}. Reduce one or more values — leaving "
                    f"some unclaimed is allowed, exceeding the source is not."
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
