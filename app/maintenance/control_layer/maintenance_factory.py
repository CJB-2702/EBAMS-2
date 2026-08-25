"""Factory: creates a complete maintenance workflow — the MaintenanceDetail (+
parent Event row via MTI) plus every Action/ActionTool/PartDemand template
instantiation cascade from a TemplateActionSet, atomically (R2: if any step
fails, the whole creation rolls back)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from app.events.control_layer.managers.asset_event_link_manager import (
    AssetEventLinkManager,
)
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventStatus, EventType
from app.maintenance.control_layer.action_factory import ActionFactory
from app.maintenance.models.templates.template_action_set import TemplateActionSet


class MaintenanceFactory:
    @classmethod
    def create_from_template(
        cls,
        *,
        template_action_set_id: int,
        domain_id: int,
        asset_id: int | None = None,
        title: str | None = None,
        maintenance_type: str = "",
        work_order_reference: str = "",
        event_start=None,
        maintenance_plan_id: int | None = None,
        assigned_user=None,
        assigned_by=None,
        priority=None,
        actor=None,
        commit: bool = True,
    ) -> MaintenanceDetail:
        template = TemplateActionSet.objects.get(
            pk=template_action_set_id, deleted_at__isnull=True
        )

        def _create() -> MaintenanceDetail:
            detail = MaintenanceDetail.objects.create(
                domain_id=domain_id,
                asset_id=asset_id,
                title=title or template.task_name,
                description=template.description,
                event_type=EventType.MAINTENANCE,
                status=EventStatus.PLANNED,
                priority=priority,
                event_start=event_start or timezone.now(),
                maintenance_type=maintenance_type,
                work_order_reference=work_order_reference,
                template_action_set=template,
                maintenance_plan_id=maintenance_plan_id,
                assigned_user=assigned_user,
                assigned_by=assigned_by,
                created_by=actor,
                updated_by=actor,
            )
            # The join row, not just the column. MaintenanceDetail.asset stays
            # authoritative for maintenance's own reads; this makes the same
            # fact visible to the events portal and to every app that asks
            # "which assets is this event about" without knowing what a
            # MaintenanceDetail is.
            AssetEventLinkManager.link(
                asset_id=asset_id, event_id=detail.pk, role="target", actor=actor
            )
            # ActionFactory expands every TemplateActionItem into a live Action
            # (+ tools, + part demands) in the SAME transaction as this row (R2).
            ActionFactory.create_from_template_action_set(
                template_action_set_id=template_action_set_id,
                maintenance_detail_id=detail.pk,
                actor=actor,
                commit=False,
            )
            return detail

        if commit:
            with transaction.atomic():
                return _create()
        return _create()

    @classmethod
    def create_blank(
        cls,
        *,
        domain_id: int,
        asset_id: int | None = None,
        title: str,
        maintenance_type: str = "",
        work_order_reference: str = "",
        event_start=None,
        priority=None,
        assigned_user=None,
        assigned_by=None,
        actor=None,
    ) -> MaintenanceDetail:
        """Create a maintenance event with no template — no Action/ActionTool/
        PartDemand rows are expanded, so the event starts with zero steps.

        Legacy had no equivalent (every creation path there required a
        TemplateActionSet — see maintenance_starter_kit incident notes); this
        exists because the edit portal's Action Creator Portal can already
        build a step list from scratch (Blank Action tab), so nothing stops a
        user starting from an empty event and adding steps as they go. The
        caller is expected to have already warned that this skips a template's
        known-good procedure.
        """
        with transaction.atomic():
            detail = MaintenanceDetail.objects.create(
                domain_id=domain_id,
                asset_id=asset_id,
                title=title,
                event_type=EventType.MAINTENANCE,
                status=EventStatus.PLANNED,
                priority=priority,
                event_start=event_start or timezone.now(),
                maintenance_type=maintenance_type,
                work_order_reference=work_order_reference,
                template_action_set=None,
                assigned_user=assigned_user,
                assigned_by=assigned_by,
                created_by=actor,
                updated_by=actor,
            )
            AssetEventLinkManager.link(
                asset_id=asset_id, event_id=detail.pk, role="target", actor=actor
            )
        return detail
