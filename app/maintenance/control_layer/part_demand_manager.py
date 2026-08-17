"""Manager: creates procurement.PartDemand rows for maintenance Actions and
links them via MaintenanceDemandLink.

D7: Maintenance owns the inward-pointing link table; PartDemand never points
back at Maintenance. This is the ONLY place in this app that creates a
PartDemand — it always goes through procurement's own PartDemandFactory
rather than PartDemand.objects.create() directly, so the four state axes and
the origin graph node initialize correctly (see PartDemandFactory.create).
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from app.maintenance.models.action import Action
from app.maintenance.models.demand_link import MaintenanceDemandLink
from app.procurement.control_layer.factories.part_demand_factory import PartDemandFactory
from app.procurement.models import DemandSourceModule


class PartDemandManager:
    @classmethod
    def create_for_action(
        cls,
        *,
        action_id: int,
        part_id: int,
        quantity_requested: Decimal,
        notes: str = "",
        expected_cost: Decimal | None = None,
        priority: str | None = None,
        requested_by=None,
        actor=None,
    ) -> MaintenanceDemandLink:
        action = Action.objects.select_related("event_detail__domain").get(
            pk=action_id, deleted_at__isnull=True
        )
        next_order = MaintenanceDemandLink.objects.filter(action_id=action_id).count() + 1

        create_kwargs = dict(
            part_id=part_id,
            domain_id=action.event_detail.domain_id,
            quantity_requested=quantity_requested,
            notes=notes,
            expected_cost=expected_cost,
            source_module=DemandSourceModule.MAINTENANCE,
            requested_by=requested_by or actor,
            actor=actor,
            commit=False,
        )
        if priority:
            create_kwargs["priority"] = priority

        with transaction.atomic():
            part_demand = PartDemandFactory.create(**create_kwargs)
            link = MaintenanceDemandLink.objects.create(
                action=action,
                part_demand=part_demand,
                sequence_order=next_order,
                created_by=actor,
                updated_by=actor,
            )
        return link

    @classmethod
    def remove_link(cls, *, link_id: int, actor=None) -> None:
        """Soft-deletes the link only — the hub PartDemand row is never deleted
        by this app (D7); its own lifecycle is owned by procurement.PartDemandContext."""
        from django.utils import timezone

        MaintenanceDemandLink.objects.filter(pk=link_id).update(
            deleted_at=timezone.now(), updated_by=actor
        )
