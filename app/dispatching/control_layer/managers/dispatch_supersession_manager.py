"""Manager: raises a new dispatch linked to an old one via
previous_dispatch — the only legal way to change frozen intent
(dispatching_starter_kit/2_dispatch.md §10, R11), and the resubmission path
after a rejection (§9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.models.details.dispatching import DispatchingDetail


class DispatchSupersessionManager:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def supersede(self, *, overrides: dict | None = None, actor: "AbstractUser") -> "DispatchingDetail":
        """Creates a new dispatch copying this one's intent fields, with any
        ``overrides`` applied, linked back via previous_dispatch. The old
        dispatch itself is not modified here — cancelling or completing it
        is a separate, explicit act by the caller."""
        overrides = overrides or {}
        source = self.dispatch
        create_kwargs = dict(
            domain_id=source.domain_id,
            requested_for_id=source.requested_for_id,
            requested_by_id=source.requested_by_id,
            desired_start=source.desired_start,
            desired_end=source.desired_end,
            asset_class_id=source.asset_class_id,
            asset_subclass_text=source.asset_subclass_text,
            headcount=source.headcount,
            names_free_text=source.names_free_text,
            requested_assets=source.requested_assets,
            dispatch_scope=source.dispatch_scope,
            estimated_meter_usage=source.estimated_meter_usage,
            activity_location=source.activity_location,
            title=source.title,
            description=source.description,
            previous_dispatch_id=source.pk,
            actor=actor,
        )
        create_kwargs.update(overrides)

        with transaction.atomic():
            new_dispatch = DispatchFactory.create(**create_kwargs)

        self._ctx._narrate(DispatchNarrator.superseded_by(new_dispatch_id=new_dispatch.pk))
        return new_dispatch
