"""Factory: instantiates a dispatch from a template's head revision —
copy, then allow deviation (dispatching_starter_kit/1_dispatch_templates.md
§7). Only head revisions can be instantiated; superseded and retired
revisions are readable but not usable (R8, R12). All or nothing: one
transaction, resolve the head, copy pre-fill values, copy all five
requirement types (four catalogue references plus material — which raises
real demands, not a private wish list; a model row's configuration template,
if any, rides along with it rather than being copied separately), and record
the exact revision as the dispatch's permanent, never-updated source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.dispatch_context import DispatchContext
from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
from app.dispatching.models.templates.dispatch_template import DispatchTemplate

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.events.models.details.dispatching import DispatchingDetail


class DispatchFromTemplateFactory:
    @classmethod
    def instantiate(
        cls,
        *,
        template_id: int,
        requested_for_id: int,
        desired_start,
        desired_end,
        requested_by_id: int | None = None,
        title: str = "",
        description: str = "",
        activity_location: str | None = None,
        actor: "AbstractUser",
    ) -> "DispatchingDetail":
        template = DispatchTemplate.objects.select_related("head_revision").get(pk=template_id)
        if template.is_retired:
            raise ValueError("This template is retired and cannot be used to raise a new dispatch.")
        revision = template.head_revision
        if revision is None:
            raise ValueError("This template has no head revision to instantiate from.")

        with transaction.atomic():
            dispatch = DispatchFactory.create(
                domain_id=template.domain_id,
                requested_for_id=requested_for_id,
                requested_by_id=requested_by_id,
                desired_start=desired_start,
                desired_end=desired_end,
                asset_class_id=revision.asset_class_id,
                asset_subclass_text=revision.asset_subclass_text,
                headcount=revision.headcount,
                dispatch_scope=revision.dispatch_scope,
                estimated_meter_usage=revision.estimated_meter_usage,
                activity_location=activity_location if activity_location is not None else revision.activity_location,
                title=title or revision.title,
                description=description,
                created_from_revision_id=revision.pk,
                actor=actor,
            )

            ctx = DispatchContext(dispatch.pk, actor)

            for capability in revision.requested_capabilities.all():
                ctx.requirements.add(
                    kind="capability", target_id=capability.capability_definition_id,
                    is_required=capability.is_required, notes=capability.notes, actor=actor,
                )
            for skill in revision.requested_skills.all():
                ctx.requirements.add(
                    kind="skill", target_id=skill.skill_id, is_required=skill.is_required,
                    notes=skill.notes, quantity=skill.quantity, minimum_level=skill.minimum_level,
                    actor=actor,
                )
            for model_req in revision.requested_models.all():
                ctx.requirements.add(
                    kind="model", target_id=model_req.model_id, is_required=model_req.is_required,
                    notes=model_req.notes, quantity=model_req.quantity,
                    configuration_template_id=model_req.configuration_template_id, actor=actor,
                )
            for modification in revision.requested_modifications.all():
                ctx.requirements.add(
                    kind="modification", target_id=modification.defined_modification_id,
                    is_required=modification.is_required, notes=modification.notes, actor=actor,
                )
            for material in revision.material_requirements.all():
                ctx.demands.raise_demand(
                    part_id=material.part_id, quantity_requested=material.quantity,
                    notes=material.notes, actor=actor,
                )

        return dispatch
