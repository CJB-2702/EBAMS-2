"""seed_maintenance_dev -- dev fixture contribution for the Maintenance kit.

Everything that has a real control-layer entrypoint goes through it, exactly
as production traffic would:

  - Procedure templates are built through TemplateBuilderSessionAdapter's
    session-draft -> commit() path (R2's atomic cascade for template
    authoring), driven from a minimal in-process session stand-in rather than
    a real HTTP request.
  - Live maintenance events (+ their Action/ActionTool/PartDemand cascade)
    are created through MaintenanceFactory/ActionFactory.
  - Blockers and asset limitation records go through
    MaintenanceContext.blocker_manager / .limitation_manager.
  - Action state transitions go through ActionContext.
  - Event completion goes through MaintenanceContext.complete(), which is
    gated by the real R4 completion policy (MaintenanceCompletionPolicy).

ProtoActionItem (+ its ProtoActionTool/ProtoPartDemand children) and
MaintenancePlan have no dedicated Factory/Manager in this app -- their real
presentation-layer entrypoints (proto_views.proto_create, planning_views.
plan_create) create them with a direct `.objects.create()` themselves, so
this seed mirrors that same direct-create shape rather than inventing a
control-layer indirection that doesn't exist in production code.

Seeds:
  - 3 ProtoActionItem library steps (oil change, cabin air filter swap,
    visual inspection checklist), two with tool + part-demand children.
  - 2 TemplateActionSet procedure templates, built via the session adapter,
    each mixing proto-sourced actions with a hand-authored one.
  - 4 MaintenanceDetail events spanning Planned, In Progress, Blocked, and
    Complete -- covering the full R4 completion path on the last one.
  - 2 MaintenanceBlocker rows: one resolved (on the Complete event, closed
    before completion), one left active (on the Blocked event).
  - 1 AssetLimitationRecord, left active, on the In Progress event.
  - 1 calendar-based MaintenancePlan (meter-based plans are not evaluated by
    MaintenancePlanner yet, per its own docstring).

Idempotent: skipped entirely once the marker-tagged proto library already
exists; safe to re-run.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand

from app.administration.models import Domain
from app.assets.models import Asset
from app.maintenance.control_layer.action_context import ActionContext
from app.maintenance.control_layer.adapters.template_builder_session_adapter import (
    TemplateBuilderSessionAdapter,
)
from app.maintenance.control_layer.maintenance_context import MaintenanceContext
from app.maintenance.control_layer.maintenance_factory import MaintenanceFactory
from app.maintenance.models.asset_limitation import CapabilityStatus
from app.maintenance.models.blocker import BlockerPriority
from app.maintenance.models.planning.maintenance_plan import (
    MaintenancePlan,
    PlanFrequencyType,
    PlanStatus,
)
from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem
from app.maintenance.models.proto_templates.proto_action_tool import ProtoActionTool
from app.maintenance.models.proto_templates.proto_part_demand import ProtoPartDemand
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.parts.models import Part, Tool

User = get_user_model()

SEED_MARKER = "[seeded by seed_maintenance_dev]"

# The parts seed_parts_dev is guaranteed to have created -- see LIGHT_PARTS in
# app/parts/management/commands/seed_parts_dev.py.
OIL_FILTER_PN = "PN-2003"
CABIN_AIR_FILTER_PN = "PN-2007"
BRAKE_PADS_PN = "PN-2001"


class _FakeSessionRequest:
    """Minimal request stand-in so TemplateBuilderSessionAdapter's session-
    draft path can be driven straight from a management command exactly as an
    HTTP request would drive it -- the adapter only ever touches
    `request.session`, never anything else on the request."""

    def __init__(self) -> None:
        self.session = SessionStore()


class Command(BaseCommand):
    help = (
        "Seed dev Maintenance data: proto action library, procedure "
        "templates, maintenance events, blockers, an asset limitation "
        "record, and a maintenance plan."
    )

    def handle(self, *args, **options):
        actor = User.objects.filter(username="generic_admin").first() or User.objects.first()
        if actor is None:
            self.stdout.write(
                self.style.WARNING(
                    "No user found -- run the dev_users fixture before "
                    "seed_maintenance_dev."
                )
            )
            return

        if ProtoActionItem.objects.filter(notes__icontains=SEED_MARKER).exists():
            self.stdout.write("Maintenance dev seed already present -- skipping.")
            return

        domain = (
            Domain.objects.filter(slug="north-acme-site-a").first()
            or Domain.objects.first()
        )
        if domain is None:
            self.stdout.write(
                self.style.WARNING(
                    "No Domain found -- run the dev_ownership fixture before "
                    "seed_maintenance_dev."
                )
            )
            return

        assets = list(
            Asset.objects.filter(domain_id=domain.pk, asset_class_id=4).order_by("id")
        )
        if len(assets) < 2:
            assets = list(Asset.objects.filter(domain_id=domain.pk).order_by("id"))
        if len(assets) < 2:
            self.stdout.write(
                self.style.WARNING(
                    "Fewer than 2 Assets exist in the target domain -- run "
                    "dev_assets_base/dev_assets_instances fixtures before "
                    "seed_maintenance_dev."
                )
            )
            return

        parts_by_number = {
            part.part_number: part
            for part in Part.objects.filter(
                part_number__in=[OIL_FILTER_PN, CABIN_AIR_FILTER_PN, BRAKE_PADS_PN]
            )
        }
        if len(parts_by_number) < 3:
            self.stdout.write(
                self.style.WARNING(
                    f"Required seed Parts ({OIL_FILTER_PN}/{CABIN_AIR_FILTER_PN}/"
                    f"{BRAKE_PADS_PN}) not found -- run seed_parts_dev before "
                    "seed_maintenance_dev."
                )
            )
            return

        tools = self._seed_tools(actor=actor)
        proto_items = self._seed_proto_library(
            actor=actor,
            domain=domain,
            tools=tools,
            oil_filter=parts_by_number[OIL_FILTER_PN],
            cabin_air_filter=parts_by_number[CABIN_AIR_FILTER_PN],
        )
        asset_class_id = assets[0].asset_class_id
        template_a, template_b = self._seed_templates(
            actor=actor,
            domain=domain,
            proto_items=proto_items,
            asset_class_id=asset_class_id,
            brake_pads=parts_by_number[BRAKE_PADS_PN],
        )
        self._seed_events(
            actor=actor,
            domain=domain,
            assets=assets,
            template_a=template_a,
            template_b=template_b,
        )
        self._seed_plan(
            actor=actor,
            domain=domain,
            template=template_a,
            asset_class_id=asset_class_id,
        )

        self.stdout.write(self.style.SUCCESS("Maintenance dev seed complete."))

    # ------------------------------------------------------------------ #
    # Tool catalog
    # ------------------------------------------------------------------ #

    def _seed_tools(self, *, actor) -> dict[str, Tool]:
        specs = [
            ("Oil Filter Wrench", "Hand Tool"),
            ("Calibrated Torque Wrench", "Hand Tool"),
            ("Digital Multimeter", "Measurement"),
        ]
        tools: dict[str, Tool] = {}
        for name, tool_type in specs:
            tool, _ = Tool.objects.get_or_create(
                name=name,
                defaults={
                    "tool_type": tool_type,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            tools[name] = tool
        return tools

    # ------------------------------------------------------------------ #
    # Proto (reusable library) action items
    # ------------------------------------------------------------------ #

    def _seed_proto_library(
        self, *, actor, domain, tools, oil_filter: Part, cabin_air_filter: Part
    ) -> dict[str, ProtoActionItem]:
        oil_change = ProtoActionItem.objects.create(
            domain=domain,
            action_name="Oil Change -- Drain and Refill",
            description="Standard engine oil drain, filter swap, and refill.",
            instructions=(
                "Drain old oil, replace the filter, refill to spec, and torque "
                "the drain plug."
            ),
            estimated_duration_minutes=30,
            minimum_staff_count=1,
            notes=f"Reusable library step. {SEED_MARKER}",
            created_by=actor,
            updated_by=actor,
        )
        ProtoActionTool.objects.create(
            proto_action_item=oil_change,
            tool=tools["Oil Filter Wrench"],
            tool_name=tools["Oil Filter Wrench"].name,
            quantity_required=1,
            is_required=True,
            sequence_order=1,
            created_by=actor,
            updated_by=actor,
        )
        ProtoPartDemand.objects.create(
            proto_action_item=oil_change,
            part=oil_filter,
            quantity_required=Decimal("1"),
            is_optional=False,
            sequence_order=1,
            notes="One filter per service interval.",
            created_by=actor,
            updated_by=actor,
        )

        air_filter_swap = ProtoActionItem.objects.create(
            domain=domain,
            action_name="Replace Cabin Air Filter",
            description="Swap the cabin air filter element.",
            instructions=(
                "Open the cabin filter housing, remove the old element, and "
                "install the new element."
            ),
            estimated_duration_minutes=15,
            minimum_staff_count=1,
            notes=f"Reusable library step. {SEED_MARKER}",
            created_by=actor,
            updated_by=actor,
        )
        ProtoPartDemand.objects.create(
            proto_action_item=air_filter_swap,
            part=cabin_air_filter,
            quantity_required=Decimal("1"),
            is_optional=False,
            sequence_order=1,
            created_by=actor,
            updated_by=actor,
        )

        inspection = ProtoActionItem.objects.create(
            domain=domain,
            action_name="Visual Inspection Checklist",
            description=(
                "Walk-around visual inspection of belts, hoses, brakes, and "
                "fluid levels."
            ),
            instructions=(
                "Check belts for cracking, hoses for leaks, brake pad wear, "
                "and fluid levels."
            ),
            estimated_duration_minutes=20,
            minimum_staff_count=1,
            required_skills="Basic mechanical inspection",
            notes=f"Reusable library step. {SEED_MARKER}",
            created_by=actor,
            updated_by=actor,
        )
        ProtoActionTool.objects.create(
            proto_action_item=inspection,
            tool=tools["Digital Multimeter"],
            tool_name=tools["Digital Multimeter"].name,
            quantity_required=1,
            is_required=False,
            sequence_order=1,
            notes="Only needed if an electrical fault is suspected during the walk-around.",
            created_by=actor,
            updated_by=actor,
        )

        return {
            "oil_change": oil_change,
            "air_filter_swap": air_filter_swap,
            "inspection": inspection,
        }

    # ------------------------------------------------------------------ #
    # Templates -- built via the real TemplateBuilderSessionAdapter path
    # ------------------------------------------------------------------ #

    def _build_template(
        self,
        *,
        actor,
        domain,
        asset_class_id: int,
        task_name: str,
        description: str,
        proto_action_ids: list[int],
        manual_actions: list[dict],
        asset_model_ids: list[int] | None = None,
    ) -> TemplateActionSet:
        request = _FakeSessionRequest()
        adapter = TemplateBuilderSessionAdapter(request)
        adapter.set_metadata(
            task_name=task_name,
            description=description,
            asset_class_id=asset_class_id,
            asset_model_ids=asset_model_ids or [],
        )
        for proto_action_item_id in proto_action_ids:
            adapter.add_action_from_proto(proto_action_item_id=proto_action_item_id)
        for manual in manual_actions:
            action = adapter.add_action(
                action_name=manual["action_name"],
                description=manual.get("description", ""),
                instructions=manual.get("instructions", ""),
                estimated_duration_minutes=manual.get("estimated_duration_minutes"),
            )
            for tool_fields in manual.get("tools", []):
                adapter.add_tool(temp_id=action["temp_id"], **tool_fields)
            for demand_fields in manual.get("part_demands", []):
                adapter.add_part_demand(temp_id=action["temp_id"], **demand_fields)
        return adapter.commit(domain_id=domain.pk, actor=actor)

    def _seed_templates(
        self, *, actor, domain, proto_items, asset_class_id: int, brake_pads: Part
    ) -> tuple[TemplateActionSet, TemplateActionSet]:
        from app.assets.models import AssetModel

        # Tag template_a with a couple of models in the class, to demonstrate
        # the multi-model case; template_b is left untagged ("any model in
        # this class"), which the UI must also render cleanly.
        seed_model_ids = list(
            AssetModel.objects.filter(asset_class_id=asset_class_id)
            .order_by("pk")
            .values_list("pk", flat=True)[:2]
        )

        template_a = self._build_template(
            actor=actor,
            domain=domain,
            asset_class_id=asset_class_id,
            task_name="Quarterly PM -- Light Vehicle",
            description="Quarterly preventive maintenance procedure for light vehicles.",
            proto_action_ids=[
                proto_items["oil_change"].pk,
                proto_items["air_filter_swap"].pk,
            ],
            asset_model_ids=seed_model_ids,
            manual_actions=[
                {
                    "action_name": "Torque Check -- Wheel Lug Nuts",
                    "description": "Verify wheel lug nut torque to spec.",
                    "instructions": (
                        "Torque all lug nuts to manufacturer spec using a "
                        "calibrated torque wrench."
                    ),
                    "estimated_duration_minutes": 15,
                    "tools": [
                        {
                            "tool_name": "Calibrated Torque Wrench",
                            "quantity_required": 1,
                            "is_required": True,
                        }
                    ],
                    "part_demands": [],
                }
            ],
        )

        template_b = self._build_template(
            actor=actor,
            domain=domain,
            asset_class_id=asset_class_id,
            task_name="Annual Deep Inspection",
            description="Annual deep inspection procedure covering safety-critical systems.",
            proto_action_ids=[proto_items["inspection"].pk],
            manual_actions=[
                {
                    "action_name": "Brake Pad Measurement",
                    "description": "Measure remaining brake pad thickness on all wheels.",
                    "instructions": (
                        "Remove wheels, measure pad thickness with calipers, "
                        "and record readings."
                    ),
                    "estimated_duration_minutes": 25,
                    "tools": [],
                    "part_demands": [
                        {
                            "part_id": brake_pads.pk,
                            "quantity_required": 4,
                            "notes": "Replace only if below wear limit.",
                            "is_optional": True,
                        }
                    ],
                }
            ],
        )
        return template_a, template_b

    # ------------------------------------------------------------------ #
    # Live maintenance events -- via MaintenanceFactory/ActionFactory
    # ------------------------------------------------------------------ #

    def _seed_events(self, *, actor, domain, assets, template_a, template_b) -> None:
        asset_a, asset_b = assets[0], assets[1]

        # 1. Planned -- created and left untouched.
        MaintenanceFactory.create_from_template(
            template_action_set_id=template_a.pk,
            domain_id=domain.pk,
            asset_id=asset_a.pk,
            title=f"Quarterly PM -- {asset_a.name}",
            maintenance_type="scheduled",
            work_order_reference="WO-SEED-0001",
            actor=actor,
        )

        # 2. In Progress -- started, first action completed, one active asset
        #    limitation record left open (never closed).
        in_progress_detail = MaintenanceFactory.create_from_template(
            template_action_set_id=template_a.pk,
            domain_id=domain.pk,
            asset_id=asset_b.pk,
            title=f"Quarterly PM -- {asset_b.name}",
            maintenance_type="scheduled",
            work_order_reference="WO-SEED-0002",
            actor=actor,
        )
        ip_context = MaintenanceContext(in_progress_detail.pk)
        ip_context.start(actor=actor)
        first_action = ip_context.struct.actions[0]
        ActionContext(first_action.pk).start(actor=actor)
        ActionContext(first_action.pk).complete(
            actor=actor, notes="Completed during seed."
        )
        ip_context.limitation_manager.create_record(
            status=CapabilityStatus.FUNCTIONAL_LIMITATIONS,
            limitation_description=(
                "Reduced load capacity pending brake inspection follow-up."
            ),
            actor=actor,
        )

        # 3. Blocked -- one active MaintenanceBlocker, left unresolved.
        blocked_detail = MaintenanceFactory.create_from_template(
            template_action_set_id=template_a.pk,
            domain_id=domain.pk,
            asset_id=asset_a.pk,
            title=f"Quarterly PM (parts hold) -- {asset_a.name}",
            maintenance_type="reactive",
            work_order_reference="WO-SEED-0003",
            actor=actor,
        )
        blocked_context = MaintenanceContext(blocked_detail.pk)
        blocked_context.start(actor=actor)
        blocked_context.blocker_manager.add_blocker(
            reason="Parts Not Available",
            notes="Waiting on cabin air filter restock.",
            priority=BlockerPriority.HIGH,
            billable_hours_lost=3.5,
            event_priority="high",
            actor=actor,
        )
        # A limitation hung off that blocker, so the dev DB carries one
        # example of the linked case: the asset is degraded AND that is the
        # reason work stopped, rather than two unrelated facts.
        blocked_context.limitation_manager.create_record(
            status=CapabilityStatus.NON_CAPABLE,
            limitation_description="Cabin air filtration offline; vehicle grounded.",
            link_to_active_blocker=True,
            actor=actor,
        )

        # 4. Complete -- one MaintenanceBlocker opened then resolved before
        #    close-out, every Action driven to Complete, then
        #    MaintenanceContext.complete() runs the real R4 completion gate.
        completed_detail = MaintenanceFactory.create_from_template(
            template_action_set_id=template_b.pk,
            domain_id=domain.pk,
            asset_id=asset_b.pk,
            title=f"Annual Deep Inspection -- {asset_b.name}",
            maintenance_type="inspection",
            work_order_reference="WO-SEED-0004",
            actor=actor,
        )
        completed_context = MaintenanceContext(completed_detail.pk)
        completed_context.start(actor=actor)
        blocker = completed_context.blocker_manager.add_blocker(
            reason="Equipment Unavailable",
            notes="Lift bay occupied; released once free.",
            priority=BlockerPriority.MEDIUM,
            billable_hours_lost=1.25,
            actor=actor,
        )
        completed_context.blocker_manager.end_blocker(
            blocker_id=blocker.pk,
            resolution_notes="Parts arrived and work resumed.",
            actor=actor,
        )
        completed_context.refresh()
        for action in completed_context.struct.actions:
            ActionContext(action.pk).start(actor=actor)
            ActionContext(action.pk).complete(
                actor=actor, notes="Completed during seed."
            )
        completed_context.refresh()
        completed_context.complete(
            actor=actor, notes="All steps verified complete during seed."
        )

    # ------------------------------------------------------------------ #
    # Recurring plan -- calendar-based only (meter-based is not evaluated
    # by MaintenancePlanner yet, per its own module docstring).
    # ------------------------------------------------------------------ #

    def _seed_plan(self, *, actor, domain, template, asset_class_id: int) -> None:
        from app.assets.models import AssetModel
        plan, created = MaintenancePlan.objects.get_or_create(
            name="Quarterly PM -- Light Vehicles",
            domain=domain,
            defaults={
                "description": (
                    "Recurring quarterly preventive maintenance for "
                    "light-vehicle class assets."
                ),
                "status": PlanStatus.ACTIVE,
                "asset_class_id": asset_class_id,
                "template_action_set": template,
                "frequency_type": PlanFrequencyType.CALENDAR,
                "delta_days": 90,
                "created_by": actor,
                "updated_by": actor,
            },
        )
        if created:
            seed_models = list(
                AssetModel.objects.filter(asset_class_id=asset_class_id).order_by("pk")[:2]
            )
            plan.asset_models.set(seed_models)
