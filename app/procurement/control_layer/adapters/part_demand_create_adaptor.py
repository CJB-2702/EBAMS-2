"""Adaptor: maps the create-demand form payload to a typed input struct."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_datetime

from app.procurement.control_layer.errors import ProcurementValidationError
from app.procurement.models import DemandPriority, DemandSourceModule, DemandState


@dataclass(frozen=True)
class PartDemandCreateInput:
    part_id: int
    domain_id: int
    quantity_requested: Decimal
    priority: str
    needed_by: object
    notes: str
    expected_cost: Decimal | None
    source_module: str
    serial_number_tracking_required: bool
    requested_by_id: int | None
    demand_state: str


class PartDemandCreateAdaptor:
    @classmethod
    def adapt(cls, post_data, *, requested_by=None) -> PartDemandCreateInput:
        errors: list[str] = []

        part_id = cls._int(post_data.get("part_id"))
        if not part_id:
            errors.append("A part is required.")

        # The domain is resolved from the requester's own assignment, never
        # asked for — except where a requester holds more than one, which is
        # the only case the form presents a choice. Either way it arrives here
        # already decided.
        domain_id = cls._int(post_data.get("domain_id"))
        if not domain_id:
            errors.append("A domain is required.")

        try:
            quantity_requested = Decimal(str(post_data.get("quantity_requested", "")).strip())
        except (InvalidOperation, ValueError):
            quantity_requested = Decimal("0")
            errors.append("A valid quantity is required.")
        if quantity_requested <= 0:
            errors.append("Quantity requested must be greater than zero.")

        priority = post_data.get("priority") or DemandPriority.MEDIUM
        if priority not in DemandPriority.values:
            errors.append("Invalid priority.")

        source_module = post_data.get("source_module") or DemandSourceModule.GENERAL
        if source_module not in DemandSourceModule.values:
            errors.append("Invalid source module.")

        # Required when a human fills in the form — they are asking for
        # something now. Projected is reachable only by an explicit caller
        # (a consumer app forecasting future work); there is no UI path to it.
        demand_state = post_data.get("demand_state") or DemandState.REQUIRED
        if demand_state not in {DemandState.REQUIRED, DemandState.PROJECTED}:
            errors.append("A demand may only open as Required or Projected.")

        expected_cost = None
        raw_cost = (post_data.get("expected_cost") or "").strip()
        if raw_cost:
            try:
                expected_cost = Decimal(raw_cost)
            except (InvalidOperation, ValueError):
                errors.append("Invalid expected cost.")

        needed_by = None
        raw_needed_by = (post_data.get("needed_by") or "").strip()
        if raw_needed_by:
            needed_by = parse_datetime(raw_needed_by)
            if needed_by is None:
                errors.append("Invalid needed-by date.")

        if errors:
            raise ProcurementValidationError(errors)

        return PartDemandCreateInput(
            part_id=part_id,
            domain_id=domain_id,
            quantity_requested=quantity_requested,
            priority=priority,
            needed_by=needed_by,
            notes=(post_data.get("notes") or "").strip(),
            expected_cost=expected_cost,
            source_module=source_module,
            serial_number_tracking_required=str(
                post_data.get("serial_number_tracking_required", "")
            ).lower()
            in {"1", "true", "on", "yes"},
            requested_by_id=getattr(requested_by, "pk", None),
            demand_state=demand_state,
        )

    @staticmethod
    def _int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
