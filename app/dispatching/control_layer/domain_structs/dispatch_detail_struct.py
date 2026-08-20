"""Struct: aggregated read model for one dispatch — header, every
requirement type, demand links, line items (reservations and expenses), and
crew. Everything the review/plan screen needs in a fixed number of queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.dispatching.models.line_items.dispatch_expense import DispatchExpense
from app.dispatching.models.line_items.dispatch_personnel import DispatchPersonnel
from app.dispatching.models.requirements.demand_link import DispatchDemandLink
from app.dispatching.models.requirements.requested_capability import (
    DispatchRequestedCapability,
)
from app.dispatching.models.requirements.requested_model import DispatchRequestedModel
from app.dispatching.models.requirements.requested_modification import (
    DispatchRequestedModification,
)
from app.dispatching.models.requirements.requested_skill import DispatchRequestedSkill
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.events.models.details.dispatching import DispatchingDetail


@dataclass
class DispatchDetailStruct:
    dispatch: DispatchingDetail
    reservations: list[AssetReservation] = field(default_factory=list)
    expenses: list[DispatchExpense] = field(default_factory=list)
    crew: list[DispatchPersonnel] = field(default_factory=list)
    requested_capabilities: list[DispatchRequestedCapability] = field(default_factory=list)
    requested_skills: list[DispatchRequestedSkill] = field(default_factory=list)
    requested_models: list[DispatchRequestedModel] = field(default_factory=list)
    requested_modifications: list[DispatchRequestedModification] = field(default_factory=list)
    demand_links: list[DispatchDemandLink] = field(default_factory=list)

    @classmethod
    def load(cls, *, dispatch_id: int) -> "DispatchDetailStruct":
        dispatch = DispatchingDetail.objects.select_related(
            "domain", "requested_for", "requested_by", "asset_class", "created_from_revision"
        ).get(pk=dispatch_id, deleted_at__isnull=True)
        return cls(
            dispatch=dispatch,
            reservations=list(
                dispatch.reservations.filter(deleted_at__isnull=True)
                .select_related("asset", "accountable_person")
                .order_by("-created_at")
            ),
            expenses=list(dispatch.expenses.order_by("-created_at")),
            crew=list(dispatch.crew.select_related("user").order_by("role")),
            requested_capabilities=list(
                dispatch.requested_capabilities.select_related("capability_definition")
            ),
            requested_skills=list(dispatch.requested_skills.select_related("skill")),
            requested_models=list(
                dispatch.requested_models.select_related("model", "configuration_template")
            ),
            requested_modifications=list(
                dispatch.requested_modifications.select_related("defined_modification")
            ),
            demand_links=list(dispatch.demand_links.select_related("part_demand")),
        )

    @property
    def dispatch_id(self) -> int:
        return self.dispatch.pk

    @property
    def live_reservations(self) -> list[AssetReservation]:
        from app.dispatching.control_layer.guards.dispatch_state_guard import (
            LIVE_RESERVATION_STATUSES,
        )

        return [r for r in self.reservations if r.reservation_status in LIVE_RESERVATION_STATUSES]

    @property
    def live_expenses(self) -> list[DispatchExpense]:
        from app.dispatching.control_layer.guards.dispatch_state_guard import (
            LIVE_EXPENSE_STATUSES,
        )

        return [e for e in self.expenses if e.status in LIVE_EXPENSE_STATUSES]

    def to_dict(self) -> dict:
        return {
            "id": self.dispatch_id,
            "title": self.dispatch.title,
            "workflow_status": self.dispatch.workflow_status,
            "requested_for_id": self.dispatch.requested_for_id,
            "reservation_count": len(self.reservations),
            "live_reservation_count": len(self.live_reservations),
            "expense_count": len(self.expenses),
            "crew_count": len(self.crew),
            "demand_link_count": len(self.demand_links),
        }
