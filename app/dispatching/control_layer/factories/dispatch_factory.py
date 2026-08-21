"""Factory: creates a dispatch header, blank or (from Step 5 on)
template-seeded. Always lands Draft (dispatching_starter_kit/2_dispatch.md
§8) — a dispatch is not in anyone's queue until submitted."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from django.utils import timezone

from app.events.models.details.dispatching import (
    DispatchingDetail,
    DispatchWorkflowStatus,
)
from app.events.models.event import ActivityThreadType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class DispatchFactory:
    @classmethod
    def create(
        cls,
        *,
        domain_id: int,
        requested_for_id: int,
        desired_start,
        desired_end,
        asset_class_id: int,
        requested_by_id: int | None = None,
        asset_subclass_text: str = "",
        headcount: int | None = None,
        names_free_text: str = "",
        requested_assets: str = "",
        dispatch_scope: str = "",
        estimated_meter_usage: float | None = None,
        activity_location: str = "",
        title: str = "",
        description: str = "",
        previous_dispatch_id: int | None = None,
        created_from_revision_id: int | None = None,
        actor: "AbstractUser",
    ) -> DispatchingDetail:
        if desired_start >= desired_end:
            raise ValueError("desired_start must be before desired_end.")

        if not title:
            title = f"Dispatch — {asset_subclass_text or 'request'}"

        now = timezone.now()
        with transaction.atomic():
            dispatch = DispatchingDetail.objects.create(
                thread_type=ActivityThreadType.EVENT,
                domain_id=domain_id,
                title=title,
                description=description,
                workflow_status=DispatchWorkflowStatus.REQUESTED,
                submitted_at=now,
                requested_for_id=requested_for_id,
                requested_by_id=requested_by_id or getattr(actor, "pk", None),
                desired_start=desired_start,
                desired_end=desired_end,
                asset_class_id=asset_class_id,
                asset_subclass_text=asset_subclass_text,
                headcount=headcount,
                names_free_text=names_free_text,
                requested_assets=requested_assets,
                dispatch_scope=dispatch_scope,
                estimated_meter_usage=estimated_meter_usage,
                activity_location=activity_location,
                previous_dispatch_id=previous_dispatch_id,
                created_from_revision_id=created_from_revision_id,
                created_by=actor,
                updated_by=actor,
            )
        return dispatch
