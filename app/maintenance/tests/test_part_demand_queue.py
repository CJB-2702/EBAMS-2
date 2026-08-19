"""The maintenance-facing part demand queue and detail page.

Covers the surface ported from the legacy manager part-demand portal
(maintenance_starter_kit/legacy_ui/gap_analysis.md §1): domain scoping, the
maintenance/all scope switch, the permission gate on every write, the bulk
verbs, and the substitution guard's refusal rules.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.administration.models import Domain
from app.events.models.details.maintenance import MaintenanceDetail
from app.events.models.event import EventType
from app.maintenance.control_layer.part_demand_manager import PartDemandManager
from app.maintenance.models.action import Action
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.control_layer.errors import TransitionRefused
from app.procurement.control_layer.factories.part_demand_factory import (
    PartDemandFactory,
)
from app.procurement.control_layer.part_demand_context import PartDemandContext
from app.procurement.models import (
    DemandSourceModule,
    DemandState,
    IssuanceState,
    PartDemand,
    PurchasingState,
)

User = get_user_model()


class PartDemandQueueTestCase(TestCase):
    """Shared fixture: one domain, two parts, one maintenance event with one
    action carrying a demand, plus one unlinked (dispatching) demand."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="pd_manager", email="pd_manager@test.local", password="TestPass123!@"
        )
        cls.reader = User.objects.create_user(
            username="pd_reader", email="pd_reader@test.local", password="TestPass123!@"
        )
        cls.outsider = User.objects.create_user(
            username="pd_outsider", email="pd_outsider@test.local", password="TestPass123!@"
        )
        cls.manager.user_permissions.add(
            Permission.objects.get(
                codename="demand_manage", content_type__app_label="procurement"
            )
        )

        cls.domain = Domain.objects.create(
            name="PD Domain", slug="pd-domain",
            created_by=cls.manager, updated_by=cls.manager,
        )
        cls.other_domain = Domain.objects.create(
            name="PD Other Domain", slug="pd-other-domain",
            created_by=cls.manager, updated_by=cls.manager,
        )

        cls.part = PartFactory.create(
            data={
                "part_number": "PN-PD-01", "name": "Oil Filter",
                "part_type": "component", "category": "test",
            },
            actor=cls.manager,
        )
        cls.replacement_part = PartFactory.create(
            data={
                "part_number": "PN-PD-02", "name": "Oil Filter (alt)",
                "part_type": "component", "category": "test",
            },
            actor=cls.manager,
        )

        cls.event = MaintenanceDetail.objects.create(
            domain=cls.domain,
            title="Oil change",
            event_type=EventType.MAINTENANCE,
            event_start=timezone.now(),
            maintenance_type="scheduled",
            assigned_user=cls.manager,
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        cls.action = Action.objects.create(
            event_detail=cls.event,
            action_name="Replace oil filter",
            sequence_order=1,
            created_by=cls.manager,
            updated_by=cls.manager,
        )
        cls.link = PartDemandManager.create_for_action(
            action_id=cls.action.pk,
            part_id=cls.part.pk,
            quantity_requested=Decimal("2"),
            actor=cls.manager,
        )
        cls.linked_demand = cls.link.part_demand

        # A demand with no maintenance link — the legacy queue showed these
        # with N/A in the event columns.
        cls.unlinked_demand = PartDemandFactory.create(
            part_id=cls.part.pk,
            domain_id=cls.domain.pk,
            quantity_requested=Decimal("1"),
            source_module=DemandSourceModule.DISPATCHING,
            actor=cls.manager,
        )
        # A demand the test users cannot see at all.
        cls.foreign_demand = PartDemandFactory.create(
            part_id=cls.part.pk,
            domain_id=cls.other_domain.pk,
            quantity_requested=Decimal("5"),
            actor=cls.manager,
        )

    def setUp(self):
        # Domain access is a login-time session snapshot, so grant it directly
        # rather than exercising the whole assignment machinery in every test.
        self.client.force_login(self.manager)
        session = self.client.session
        session["user_domain_ids"] = [self.domain.pk]
        session.save()

    def _login_as(self, user, domain_ids=None):
        self.client.force_login(user)
        session = self.client.session
        session["user_domain_ids"] = (
            [self.domain.pk] if domain_ids is None else domain_ids
        )
        session.save()


class QueueScopingTests(PartDemandQueueTestCase):
    def test_default_scope_shows_only_maintenance_linked_demands(self):
        response = self.client.get(reverse("part_demand_index"))
        self.assertEqual(response.status_code, 200)
        ids = {d.pk for d in response.context["demands"]}
        self.assertIn(self.linked_demand.pk, ids)
        self.assertNotIn(self.unlinked_demand.pk, ids)

    def test_all_scope_also_shows_unlinked_demands(self):
        response = self.client.get(reverse("part_demand_index"), {"scope": "all"})
        ids = {d.pk for d in response.context["demands"]}
        self.assertIn(self.linked_demand.pk, ids)
        self.assertIn(self.unlinked_demand.pk, ids)

    def test_demands_outside_the_users_domains_are_never_listed(self):
        response = self.client.get(reverse("part_demand_index"), {"scope": "all"})
        ids = {d.pk for d in response.context["demands"]}
        self.assertNotIn(self.foreign_demand.pk, ids)

    def test_queue_row_carries_its_event_and_action_context(self):
        response = self.client.get(reverse("part_demand_index"))
        row = next(
            d for d in response.context["demands"] if d.pk == self.linked_demand.pk
        )
        self.assertEqual(row.maintenance_row["event"].pk, self.event.pk)
        self.assertEqual(row.maintenance_row["action"].pk, self.action.pk)

    def test_unknown_scope_falls_back_to_maintenance_rather_than_erroring(self):
        response = self.client.get(reverse("part_demand_index"), {"scope": "nonsense"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filters"]["scope"], "maintenance")

    def test_approval_status_filter_narrows_the_queue(self):
        PartDemandContext(self.linked_demand.pk).approve(actor=self.manager)
        response = self.client.get(
            reverse("part_demand_index"),
            {"scope": "all", "demand_state": DemandState.APPROVED},
        )
        ids = {d.pk for d in response.context["demands"]}
        self.assertEqual(ids, {self.linked_demand.pk})

    def test_htmx_results_format_returns_the_fragment_not_the_page(self):
        response = self.client.get(
            reverse("part_demand_index"), {"format": "htmx-search-results"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")

    def test_sort_parameter_is_whitelisted_not_passed_through(self):
        # A hostile sort value must not reach order_by.
        response = self.client.get(
            reverse("part_demand_index"), {"sort": "domain__name; DROP"}
        )
        self.assertEqual(response.status_code, 200)


class QueuePermissionTests(PartDemandQueueTestCase):
    def test_reader_without_demand_manage_sees_the_queue_read_only(self):
        self._login_as(self.reader)
        response = self.client.get(reverse("part_demand_index"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_manage"])

    def test_reader_cannot_bulk_approve(self):
        self._login_as(self.reader)
        response = self.client.post(
            reverse("part_demand_index"),
            {"action": "bulk_approve", "demand_ids": [self.linked_demand.pk]},
        )
        self.assertEqual(response.status_code, 403)
        self.linked_demand.refresh_from_db()
        self.assertNotEqual(self.linked_demand.demand_state, DemandState.APPROVED)

    def test_user_with_no_domains_sees_an_empty_queue(self):
        self._login_as(self.outsider, domain_ids=[])
        response = self.client.get(reverse("part_demand_index"), {"scope": "all"})
        self.assertEqual(len(response.context["demands"]), 0)


class BulkActionTests(PartDemandQueueTestCase):
    def test_bulk_approve_moves_every_checked_demand(self):
        response = self.client.post(
            reverse("part_demand_index"),
            {
                "action": "bulk_approve",
                "demand_ids": [self.linked_demand.pk, self.unlinked_demand.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        for demand in (self.linked_demand, self.unlinked_demand):
            demand.refresh_from_db()
            self.assertEqual(demand.demand_state, DemandState.APPROVED)

    def test_bulk_reject_moves_every_checked_demand(self):
        self.client.post(
            reverse("part_demand_index"),
            {"action": "bulk_reject", "demand_ids": [self.linked_demand.pk]},
        )
        self.linked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.demand_state, DemandState.REJECTED)

    def test_row_action_acts_only_on_its_own_row(self):
        """The per-row button posts verb and id in one value; anything checked
        elsewhere on the page must be ignored."""
        self.client.post(
            reverse("part_demand_index"),
            {
                "row_action": f"bulk_approve:{self.linked_demand.pk}",
                "demand_ids": [self.unlinked_demand.pk],
            },
        )
        self.linked_demand.refresh_from_db()
        self.unlinked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.demand_state, DemandState.APPROVED)
        self.assertNotEqual(self.unlinked_demand.demand_state, DemandState.APPROVED)

    def test_posted_ids_outside_the_users_domains_are_skipped(self):
        self.client.post(
            reverse("part_demand_index"),
            {
                "action": "bulk_approve",
                "demand_ids": [self.linked_demand.pk, self.foreign_demand.pk],
            },
        )
        self.foreign_demand.refresh_from_db()
        self.assertNotEqual(self.foreign_demand.demand_state, DemandState.APPROVED)

    def test_bulk_with_no_selection_reports_rather_than_crashing(self):
        response = self.client.post(
            reverse("part_demand_index"), {"action": "bulk_approve"}
        )
        self.assertEqual(response.status_code, 302)

    def test_bulk_over_the_limit_is_refused_not_truncated(self):
        response = self.client.post(
            reverse("part_demand_index"),
            {"action": "bulk_approve", "demand_ids": list(range(1, 500))},
        )
        self.assertEqual(response.status_code, 302)
        self.linked_demand.refresh_from_db()
        self.assertNotEqual(self.linked_demand.demand_state, DemandState.APPROVED)

    def test_unknown_bulk_action_changes_nothing(self):
        self.client.post(
            reverse("part_demand_index"),
            {"action": "bulk_delete_everything", "demand_ids": [self.linked_demand.pk]},
        )
        self.linked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.demand_state, DemandState.REQUIRED)

    def test_bulk_substitute_part_swaps_the_requested_part(self):
        self.client.post(
            reverse("part_demand_index"),
            {
                "action": "bulk_substitute_part",
                "demand_ids": [self.linked_demand.pk],
                "new_part_id": self.replacement_part.pk,
            },
        )
        self.linked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.part_id, self.replacement_part.pk)

    def test_bulk_substitute_without_a_part_does_nothing(self):
        self.client.post(
            reverse("part_demand_index"),
            {"action": "bulk_substitute_part", "demand_ids": [self.linked_demand.pk]},
        )
        self.linked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.part_id, self.part.pk)


class SubstitutionGuardTests(PartDemandQueueTestCase):
    """The substitution verb is the one write here that is not a state
    transition, so its guard is the only thing standing between a manager and
    a graph whose members disagree about the part."""

    def test_substitution_records_a_trace_in_notes(self):
        PartDemandContext(self.linked_demand.pk).substitute_part(
            new_part_id=self.replacement_part.pk, actor=self.manager, notes="out of stock"
        )
        self.linked_demand.refresh_from_db()
        self.assertIn("Part substituted", self.linked_demand.notes)
        self.assertIn("out of stock", self.linked_demand.notes)

    def test_substitution_refreshes_the_graphs_cached_part(self):
        demand = self.linked_demand
        PartDemandContext(demand.pk).substitute_part(
            new_part_id=self.replacement_part.pk, actor=self.manager
        )
        demand.refresh_from_db()
        demand.graph.refresh_from_db()
        self.assertEqual(demand.graph.part_id, self.replacement_part.pk)

    def test_substituting_for_the_same_part_is_refused(self):
        with self.assertRaises(TransitionRefused):
            PartDemandContext(self.linked_demand.pk).substitute_part(
                new_part_id=self.part.pk, actor=self.manager
            )

    def test_substitution_is_refused_once_a_purchasing_decision_exists(self):
        PartDemand.objects.filter(pk=self.linked_demand.pk).update(
            purchasing_state=PurchasingState.APPROVED
        )
        with self.assertRaises(TransitionRefused) as caught:
            PartDemandContext(self.linked_demand.pk).substitute_part(
                new_part_id=self.replacement_part.pk, actor=self.manager
            )
        self.assertIn("purchasing", str(caught.exception).lower())

    def test_substitution_is_refused_once_anything_is_on_order(self):
        PartDemand.objects.filter(pk=self.linked_demand.pk).update(
            purchased_qty=Decimal("1")
        )
        with self.assertRaises(TransitionRefused):
            PartDemandContext(self.linked_demand.pk).substitute_part(
                new_part_id=self.replacement_part.pk, actor=self.manager
            )

    def test_substitution_is_refused_once_anything_is_issued(self):
        PartDemand.objects.filter(pk=self.linked_demand.pk).update(
            issuance_state=IssuanceState.ISSUED, issued_qty=Decimal("2")
        )
        with self.assertRaises(TransitionRefused):
            PartDemandContext(self.linked_demand.pk).substitute_part(
                new_part_id=self.replacement_part.pk, actor=self.manager
            )

    def test_substitution_is_refused_on_a_cancelled_demand(self):
        PartDemand.objects.filter(pk=self.linked_demand.pk).update(
            demand_state=DemandState.CANCELLED
        )
        with self.assertRaises(TransitionRefused):
            PartDemandContext(self.linked_demand.pk).substitute_part(
                new_part_id=self.replacement_part.pk, actor=self.manager
            )

    def test_a_refused_row_is_skipped_and_named_without_failing_the_batch(self):
        PartDemand.objects.filter(pk=self.unlinked_demand.pk).update(
            purchased_qty=Decimal("1")
        )
        response = self.client.post(
            reverse("part_demand_index"),
            {
                "action": "bulk_substitute_part",
                "demand_ids": [self.linked_demand.pk, self.unlinked_demand.pk],
                "new_part_id": self.replacement_part.pk,
            },
            follow=True,
        )
        self.linked_demand.refresh_from_db()
        self.unlinked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.part_id, self.replacement_part.pk)
        self.assertEqual(self.unlinked_demand.part_id, self.part.pk)
        body = response.content.decode()
        self.assertIn("1 demand(s) updated.", body)
        self.assertIn(f"Demand #{self.unlinked_demand.pk}", body)


class DetailPageTests(PartDemandQueueTestCase):
    def test_detail_renders_the_maintenance_context_for_a_linked_demand(self):
        response = self.client.get(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_maintenance_link"])
        self.assertContains(response, "Replace oil filter")

    def test_detail_renders_an_explicit_empty_state_for_an_unlinked_demand(self):
        """Rule #5: the Maintenance Context card renders either way."""
        response = self.client.get(
            reverse("part_demand_detail", kwargs={"pk": self.unlinked_demand.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["has_maintenance_link"])
        self.assertContains(response, "not linked to a maintenance action")
        self.assertContains(response, "Maintenance Context")

    def test_detail_shows_both_approval_gates_independently(self):
        response = self.client.get(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk})
        )
        self.assertContains(response, "Maintenance approval")
        self.assertContains(response, "Supply / purchasing")

    def test_a_demand_outside_the_users_domains_is_not_reachable(self):
        response = self.client.get(
            reverse("part_demand_detail", kwargs={"pk": self.foreign_demand.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_approve_from_the_detail_page(self):
        self.client.post(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk}),
            {"action": "approve", "notes": "needed for WO-1"},
        )
        self.linked_demand.refresh_from_db()
        self.assertEqual(self.linked_demand.demand_state, DemandState.APPROVED)

    def test_reader_cannot_approve_from_the_detail_page(self):
        self._login_as(self.reader)
        response = self.client.post(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk}),
            {"action": "approve"},
        )
        self.assertEqual(response.status_code, 403)

    def test_refusal_is_surfaced_as_a_named_message_not_a_500(self):
        PartDemand.objects.filter(pk=self.linked_demand.pk).update(
            demand_state=DemandState.CANCELLED
        )
        response = self.client.post(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk}),
            {"action": "substitute_part", "new_part_id": self.replacement_part.pk},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Demand #{self.linked_demand.pk}")

    def test_part_search_fragment_returns_selectable_rows(self):
        response = self.client.get(
            reverse("part_demand_detail", kwargs={"pk": self.linked_demand.pk}),
            {"format": "htmx-part-search", "q": "PN-PD-02"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-value="{self.replacement_part.pk}"')
        self.assertNotContains(response, "PN-PD-01")
