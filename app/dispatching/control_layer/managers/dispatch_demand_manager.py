"""Manager: raises real, issuable material demands into the shared
procurement hub and links them to the dispatch — mirrors
maintenance.PartDemandManager exactly (dispatching_starter_kit/2_dispatch.md
§7). Dispatching never writes a stock movement itself, and never decides
what cancelling a demand means (§13) — cancellation is delegated entirely to
PartDemandContext and its own gates.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.dispatching.models.requirements.demand_link import DispatchDemandLink

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchDemandManager:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def raise_demand(
        self,
        *,
        part_id: int,
        quantity_requested: Decimal,
        notes: str = "",
        expected_cost: Decimal | None = None,
        priority: str | None = None,
        actor: "AbstractUser",
    ) -> DispatchDemandLink:
        IntentLockPolicy.check_editable(dispatch=self.dispatch)

        from app.procurement.control_layer.factories.part_demand_factory import (
            PartDemandFactory,
        )
        from app.procurement.models import DemandSourceModule

        create_kwargs = dict(
            part_id=part_id,
            domain_id=self.dispatch.domain_id,
            quantity_requested=quantity_requested,
            notes=notes,
            expected_cost=expected_cost,
            source=DemandSourceModule.DISPATCHING,
            event_id=self.dispatch.id,
            requested_by=self.dispatch.requested_for,
            actor=actor,
            commit=False,
        )
        if priority:
            create_kwargs["priority"] = priority

        with transaction.atomic():
            demand = PartDemandFactory.create(**create_kwargs)
            link = DispatchDemandLink.objects.create(
                dispatch=self.dispatch,
                part_demand=demand,
                created_by=actor,
                updated_by=actor,
            )

        self._ctx._narrate(
            DispatchNarrator.demand_raised(
                part_number=demand.part.part_number, quantity=quantity_requested
            )
        )
        self._ctx.refresh()
        return link

    def cancel_all_unissued(self, *, actor: "AbstractUser", reason: str) -> list[dict]:
        """Cancels every demand link's PartDemand that the hub will let go.
        Never overrides a refusal — collects and reports it instead
        (doc 2 §13: "the refusal stands")."""
        from app.procurement.control_layer.errors import TransitionRefused
        from app.procurement.control_layer.part_demand_context import PartDemandContext

        results: list[dict] = []
        for link in self.dispatch.demand_links.select_related("part_demand").all():
            try:
                PartDemandContext(link.part_demand_id).cancel(actor=actor, notes=reason)
                results.append({"part_demand_id": link.part_demand_id, "cancelled": True})
            except TransitionRefused as exc:
                results.append(
                    {"part_demand_id": link.part_demand_id, "cancelled": False, "reason": str(exc)}
                )
        return results
