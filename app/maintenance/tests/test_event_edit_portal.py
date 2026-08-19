"""The event edit portal (maintenance_starter_kit/legacy_ui/page_catalog.md
entry 21, legacy /maintenance-event/<id>/edit). Covers the verbs added when
porting the page: event metadata save, per-action field save, and the
per-action parts/tools management that the legacy page hosted directly on
this screen (rather than punting to the work portal).
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action, ActionStatus
from app.maintenance.models.action_tool import ActionTool
from app.maintenance.models.demand_link import MaintenanceDemandLink
from app.parts.control_layer.factories.part_factory import PartFactory
from app.parts.models import Tool

User = get_user_model()


class EventEditPortalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="edit_manager", email="edit_manager@test.local", password="TestPass123!@"
        )
        cls.outsider = User.objects.create_user(
            username="edit_outsider", email="edit_outsider@test.local", password="TestPass123!@"
        )
        cls.domain = Domain.objects.create(
            name="Edit Domain", slug="edit-domain",
            created_by=cls.manager, updated_by=cls.manager,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-EDIT-01", "name": "Brake Pad Set",
                "part_type": "component", "category": "test",
            },
            actor=cls.manager,
        )
        cls.tool = Tool.objects.create(
            name="Torque Wrench", created_by=cls.manager, updated_by=cls.manager,
        )
        cls.event = MaintenanceDetail.objects.create(
            domain=cls.domain,
            title="Brake inspection",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            status="in_progress",
            assigned_user=cls.manager,
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        cls.action = Action.objects.create(
            event_detail=cls.event,
            action_name="Check brake pads",
            sequence_order=1,
            created_by=cls.manager,
            updated_by=cls.manager,
        )

    def setUp(self):
        self.client.force_login(self.manager)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def _login_as(self, user, domain_ids=None):
        self.client.force_login(user)
        session = self.client.session
        session["user_domain_ids"] = [] if domain_ids is None else domain_ids
        session.save()

    def _edit_url(self):
        return reverse("maintenance_edit", kwargs={"pk": self.event.pk})


class RenderTests(EventEditPortalTestCase):
    def test_page_renders_for_a_user_in_domain(self):
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check brake pads")

    def test_action_creator_tabs_render_not_blank(self):
        """Regression: the GET context previously omitted `tabs`, so the tab
        strip in the embedded Action Creator Portal silently rendered empty."""
        response = self.client.get(self._edit_url())
        self.assertContains(response, "From Template")
        self.assertContains(response, "Blank Action")

    def test_event_outside_the_users_domain_is_a_404(self):
        self._login_as(self.outsider, domain_ids=[])
        response = self.client.get(self._edit_url())
        self.assertEqual(response.status_code, 404)

    def test_first_action_is_selected_by_default_with_no_selected_param(self):
        """Regression: the panel opened empty until a user clicked a row;
        legacy defaults to the first action (render_edit_page)."""
        response = self.client.get(self._edit_url())
        self.assertEqual(response.context["selected_action"].pk, self.action.pk)

    def test_explicit_selected_param_still_wins(self):
        second = Action.objects.create(
            event_detail=self.event, action_name="Bleed brake lines",
            sequence_order=2, created_by=self.manager, updated_by=self.manager,
        )
        response = self.client.get(self._edit_url(), {"selected": second.pk})
        self.assertEqual(response.context["selected_action"].pk, second.pk)

    def test_action_creator_portal_is_not_empty_on_first_load(self):
        """Regression: template_sets/etc. were only ever populated inside the
        htmx tab-switch fragment view, never on the initial full-page GET —
        so the embedded Action Creator Portal always opened empty until the
        user clicked a tab (which reloads the exact same tab)."""
        from app.maintenance.models.templates.template_action_set import (
            TemplateActionSet,
        )

        TemplateActionSet.objects.create(
            domain=self.domain, task_name="Brake Inspection", is_active=True,
            created_by=self.manager, updated_by=self.manager,
        )
        response = self.client.get(self._edit_url())
        self.assertIn("Brake Inspection", [t.task_name for t in response.context["template_sets"]])


class SaveEventTests(EventEditPortalTestCase):
    def test_save_event_updates_title_and_end_date(self):
        response = self.client.post(
            self._edit_url(),
            {
                "action": "save_event",
                "title": "Brake inspection (updated)",
                "description": self.event.description,
                "work_order_reference": "WO-1",
                "maintenance_type": "scheduled",
                "priority": "medium",
                "event_end": "2026-09-01T10:00",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.title, "Brake inspection (updated)")
        self.assertIsNotNone(self.event.event_end)


class SaveEventAdditionalDetailsTests(EventEditPortalTestCase):
    """The legacy "Additional Details" collapsible on the metadata form.
    Only fields that actually exist on the live MaintenanceDetail row are
    ported here — estimated_duration/safety_review_required/staff_count/
    labor_hours/parts_cost live only on AbstractActionSet (TemplateActionSet),
    not on the live event, so they're deliberately not exposed."""

    def test_save_event_updates_actual_billable_hours_and_notes(self):
        response = self.client.post(
            self._edit_url(),
            {
                "action": "save_event",
                "actual_billable_hours": "3.5",
                "completion_notes": "all torque specs verified",
                "blocker_notes": "waiting on brake pad restock",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.event.refresh_from_db()
        self.assertEqual(self.event.actual_billable_hours, 3.5)
        self.assertEqual(self.event.completion_notes, "all torque specs verified")
        self.assertEqual(self.event.blocker_notes, "waiting on brake pad restock")


class SaveActionTests(EventEditPortalTestCase):
    def test_save_action_updates_status_and_new_fields(self):
        response = self.client.post(
            self._edit_url(),
            {
                "action": "save_action",
                "action_id": self.action.pk,
                "action_name": "Check brake pads",
                "status": ActionStatus.IN_PROGRESS,
                "estimated_duration_minutes": "45",
                "billable_hours": "0.75",
                "notes": "torn boot noted",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, ActionStatus.IN_PROGRESS)
        self.assertEqual(self.action.estimated_duration_minutes, 45)
        self.assertEqual(self.action.billable_hours, 0.75)
        self.assertEqual(self.action.notes, "torn boot noted")

    def test_save_action_with_a_changed_sequence_order_reorders_siblings(self):
        second = Action.objects.create(
            event_detail=self.event, action_name="Torque wheel nuts",
            sequence_order=2, created_by=self.manager, updated_by=self.manager,
        )
        response = self.client.post(
            self._edit_url(),
            {
                "action": "save_action",
                "action_id": self.action.pk,
                "action_name": "Check brake pads",
                "sequence_order": "2",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.action.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.action.sequence_order, 2)
        self.assertEqual(second.sequence_order, 1)

    def test_save_action_with_an_unchanged_sequence_order_does_not_reorder(self):
        response = self.client.post(
            self._edit_url(),
            {
                "action": "save_action",
                "action_id": self.action.pk,
                "action_name": "Check brake pads",
                "sequence_order": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.action.refresh_from_db()
        self.assertEqual(self.action.sequence_order, 1)


class ActionToolTests(EventEditPortalTestCase):
    def test_add_action_tool_from_catalog(self):
        response = self.client.post(
            self._edit_url(),
            {"action": "add_action_tool", "action_id": self.action.pk,
             "tool_id": self.tool.pk, "quantity_required": "2"},
        )
        self.assertEqual(response.status_code, 302)
        row = ActionTool.objects.get(action_id=self.action.pk, deleted_at__isnull=True)
        self.assertEqual(row.tool_id, self.tool.pk)
        self.assertEqual(row.quantity_required, 2)

    def test_add_action_tool_ad_hoc(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_action_tool", "action_id": self.action.pk,
             "tool_name": "Shop rag", "quantity_required": "1"},
        )
        row = ActionTool.objects.get(action_id=self.action.pk, deleted_at__isnull=True)
        self.assertEqual(row.tool_name, "Shop rag")

    def test_remove_action_tool_soft_deletes(self):
        row = ActionTool.objects.create(
            action=self.action, tool_name="Old jack", quantity_required=1,
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.post(
            self._edit_url(), {"action": "remove_action_tool", "action_tool_id": row.pk}
        )
        row.refresh_from_db()
        self.assertIsNotNone(row.deleted_at)

    def test_edit_action_tool_updates_quantity_and_specifications(self):
        row = ActionTool.objects.create(
            action=self.action, tool_name="Old jack", quantity_required=1,
            created_by=self.manager, updated_by=self.manager,
        )
        self.client.post(
            self._edit_url(),
            {"action": "edit_action_tool", "action_tool_id": row.pk,
             "quantity_required": "3", "specifications": "3-ton capacity", "notes": "borrowed"},
        )
        row.refresh_from_db()
        self.assertEqual(row.quantity_required, 3)
        self.assertEqual(row.specifications, "3-ton capacity")
        self.assertEqual(row.notes, "borrowed")


class ActionPartDemandTests(EventEditPortalTestCase):
    def test_add_action_part_demand_creates_the_link(self):
        response = self.client.post(
            self._edit_url(),
            {"action": "add_action_part_demand", "action_id": self.action.pk,
             "part_id": self.part.pk, "quantity": "2", "priority": "high"},
        )
        self.assertEqual(response.status_code, 302)
        link = MaintenanceDemandLink.objects.get(
            action_id=self.action.pk, deleted_at__isnull=True
        )
        self.assertEqual(link.part_demand.part_id, self.part.pk)
        self.assertEqual(link.part_demand.quantity_requested, Decimal("2"))

    def test_remove_action_part_demand_soft_deletes_the_link_only(self):
        link = PartDemandManager.create_for_action(
            action_id=self.action.pk, part_id=self.part.pk,
            quantity_requested=Decimal("1"), actor=self.manager,
        )
        demand_pk = link.part_demand_id
        self.client.post(
            self._edit_url(), {"action": "remove_action_part_demand", "link_id": link.pk}
        )
        link.refresh_from_db()
        self.assertIsNotNone(link.deleted_at)
        # The hub PartDemand row itself is untouched — D7, owned by procurement.
        from app.procurement.models import PartDemand
        self.assertTrue(PartDemand.objects.filter(pk=demand_pk, deleted_at__isnull=True).exists())


class BlockerAndLimitationTests(EventEditPortalTestCase):
    def test_add_blocker_moves_event_to_blocked(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_blocker", "reason": "Parts Not Available", "priority": "High"},
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "blocked")

    def test_end_blocker_returns_event_to_in_progress(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_blocker", "reason": "Parts Not Available", "priority": "High"},
        )
        self.event.refresh_from_db()
        blocker = self.event.blockers.get()
        self.client.post(
            self._edit_url(),
            {
                "action": "end_blocker",
                "blocker_id": blocker.pk,
                "resolution_notes": "Parts arrived",
            },
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, "in_progress")

    def test_a_blocker_cannot_be_resolved_without_a_reason(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_blocker", "reason": "Parts Not Available", "priority": "High"},
        )
        blocker = self.event.blockers.get()
        self.client.post(
            self._edit_url(), {"action": "end_blocker", "blocker_id": blocker.pk}
        )
        blocker.refresh_from_db()
        self.assertIsNone(blocker.end_date)

    def test_add_and_close_limitation(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_limitation", "status": "Non Capable",
             "limitation_description": "Cracked rotor"},
        )
        from app.maintenance.models.asset_limitation import AssetLimitationRecord
        record = AssetLimitationRecord.objects.get(maintenance_detail_id=self.event.pk)
        self.assertIsNone(record.end_time)
        self.client.post(
            self._edit_url(),
            {
                "action": "close_limitation",
                "record_id": record.pk,
                "resolution_notes": "Rotor replaced",
            },
        )
        record.refresh_from_db()
        self.assertIsNotNone(record.end_time)
        self.assertEqual(record.resolution_notes, "Rotor replaced")

    def test_a_limitation_cannot_be_closed_without_a_reason(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_limitation", "status": "Non Capable",
             "limitation_description": "Cracked rotor"},
        )
        from app.maintenance.models.asset_limitation import AssetLimitationRecord
        record = AssetLimitationRecord.objects.get(maintenance_detail_id=self.event.pk)
        self.client.post(
            self._edit_url(), {"action": "close_limitation", "record_id": record.pk}
        )
        record.refresh_from_db()
        self.assertIsNone(record.end_time)

    def test_edit_limitation_updates_the_description_while_still_active(self):
        from app.maintenance.models.asset_limitation import AssetLimitationRecord

        self.client.post(
            self._edit_url(),
            {"action": "add_limitation", "status": "Non Capable",
             "limitation_description": "Cracked rotor"},
        )
        record = AssetLimitationRecord.objects.get(maintenance_detail_id=self.event.pk)
        self.client.post(
            self._edit_url(),
            {"action": "edit_limitation", "record_id": record.pk,
             "status": "Non Capable", "limitation_description": "Cracked rotor, confirmed on inspection"},
        )
        record.refresh_from_db()
        self.assertEqual(record.limitation_description, "Cracked rotor, confirmed on inspection")
        self.assertIsNone(record.end_time)

    def test_edit_blocker_updates_reason_and_priority(self):
        self.client.post(
            self._edit_url(),
            {"action": "add_blocker", "reason": "Parts Not Available", "priority": "Medium"},
        )
        blocker = self.event.blockers.get()
        self.client.post(
            self._edit_url(),
            {"action": "edit_blocker", "blocker_id": blocker.pk,
             "reason": "Equipment Unavailable", "priority": "High", "notes": "lift is down"},
        )
        blocker.refresh_from_db()
        self.assertEqual(blocker.reason, "Equipment Unavailable")
        self.assertEqual(blocker.priority, "High")
        self.assertEqual(blocker.notes, "lift is down")
