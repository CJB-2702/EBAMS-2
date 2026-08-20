"""Presentation-layer tests for the reservation screens.

These cover the three things the views own that the control layer cannot:
the permission gate on each route, the domain fence resolving to 404 rather
than 403 (5_roles_and_permissions.md §4), and the split between a permission
failure (403) and a state failure (a message on a 200).

The lifecycle itself is already covered by test_reservation_lifecycle.py —
what is tested here is the HTTP surface over it.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from app.administration.auth_session import (
    SESSION_KEY_DOMAIN_IDS,
    SESSION_KEY_PERMISSION_CODENAMES,
)
from app.dispatching.control_layer.factories.reservation_factory import ReservationFactory
from app.dispatching.models.enums import ReservationStatus, ReservationType
from app.dispatching.models.reservations.asset_reservation import AssetReservation
from app.dispatching.tests.base import DispatchingTestCase

RESERVATION_PERMS = (
    "reservation_book", "reservation_confirm",
    "reservation_self_service", "reservation_verify",
)


class ReservationViewTestCase(DispatchingTestCase):
    """Adds HTTP plumbing to the shared dispatching fixture."""

    def _grant(self, user, *codenames: str) -> None:
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(codename=codename))
        user.refresh_from_db()
        # has_perm() caches per instance; drop it so the grant takes effect.
        for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            if hasattr(user, attr):
                delattr(user, attr)

    def _login(self, user, *, domain_ids=None):
        """Log in and prime the login-time session snapshot the domain fence
        reads (D5) — force_login does not run our auth signal."""
        self.client.force_login(user)
        session = self.client.session
        session[SESSION_KEY_DOMAIN_IDS] = (
            list(domain_ids) if domain_ids is not None else [self.domain.pk]
        )
        session[SESSION_KEY_PERMISSION_CODENAMES] = sorted(user.get_all_permissions())
        session.save()

    def _make_reservation(self, *, accountable=None, days_out: int = 1) -> AssetReservation:
        start = timezone.now() + timedelta(days=days_out)
        return ReservationFactory.create(
            asset_id=self.asset.pk,
            domain_id=self.domain.pk,
            reservation_type=ReservationType.WORK,
            accountable_person_id=(accountable or self.actor).pk,
            scheduled_start=start,
            scheduled_end=start + timedelta(days=2),
            actor=self.actor,
        )


class ReservationAccessTests(ReservationViewTestCase):
    def test_index_requires_a_reservation_permission(self):
        self._login(self.other_user)
        response = self.client.get(reverse("dispatching_reservation_index"))
        self.assertEqual(response.status_code, 403)

    def test_index_renders_for_a_booker(self):
        self._grant(self.actor, "reservation_book")
        self._login(self.actor)
        response = self.client.get(reverse("dispatching_reservation_index"))
        self.assertEqual(response.status_code, 200)

    def test_detail_outside_the_users_domains_is_404_not_403(self):
        """R3: a user who may not see a record must not learn it exists."""
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book")
        self._login(self.actor, domain_ids=[])  # permission held, no domains
        response = self.client.get(
            reverse("dispatching_reservation_detail", kwargs={"pk": reservation.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_edit_is_refused_without_the_dispatch_manager_marker(self):
        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS)
        self._login(self.actor)
        response = self.client.get(
            reverse("dispatching_reservation_edit", kwargs={"pk": reservation.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_edit_is_allowed_for_a_dispatch_manager(self):
        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS, "template_commit")
        self._login(self.actor)
        response = self.client.get(
            reverse("dispatching_reservation_edit", kwargs={"pk": reservation.pk})
        )
        self.assertEqual(response.status_code, 200)


class ReservationDetailIsReadOnlyTests(ReservationViewTestCase):
    def test_detail_refuses_post(self):
        """The view-only route must have no write path at all."""
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book")
        self._login(self.actor)
        response = self.client.post(
            reverse("dispatching_reservation_detail", kwargs={"pk": reservation.pk}),
            {"action": "confirm"},
        )
        self.assertEqual(response.status_code, 405)
        reservation.refresh_from_db()
        self.assertEqual(reservation.reservation_status, ReservationStatus.TENTATIVE)


class ReservationCreateTests(ReservationViewTestCase):
    def test_create_lands_tentative(self):
        self._grant(self.actor, "reservation_book")
        self._login(self.actor)
        start = timezone.now() + timedelta(days=30)
        response = self.client.post(reverse("dispatching_reservation_create"), {
            "asset_id": self.asset.pk,
            "scheduled_start": timezone.localtime(start).strftime("%Y-%m-%dT%H:%M"),
            "scheduled_end": timezone.localtime(start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "reservation_type": ReservationType.WORK,
            "accountable_person_id": self.actor.pk,
            "title": "View-created booking",
        })
        self.assertEqual(response.status_code, 302)
        reservation = AssetReservation.objects.get(title="View-created booking")
        self.assertEqual(reservation.reservation_status, ReservationStatus.TENTATIVE)

    def test_create_refuses_an_asset_outside_the_users_domains(self):
        self._grant(self.actor, "reservation_book")
        self._login(self.actor, domain_ids=[])
        start = timezone.now() + timedelta(days=30)
        response = self.client.post(reverse("dispatching_reservation_create"), {
            "asset_id": self.asset.pk,
            "scheduled_start": timezone.localtime(start).strftime("%Y-%m-%dT%H:%M"),
            "scheduled_end": timezone.localtime(start + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "reservation_type": ReservationType.WORK,
            "accountable_person_id": self.actor.pk,
            "title": "Should not exist",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(AssetReservation.objects.filter(title="Should not exist").exists())


class ReservationLifecycleRouteTests(ReservationViewTestCase):
    """Confirm / cancel / no-show. The controls render on the detail page but
    post here, which is what lets that page stay GET-only."""

    def _lifecycle(self, reservation):
        return reverse("dispatching_reservation_lifecycle", kwargs={"pk": reservation.pk})

    def test_confirm_promotes_a_tentative_booking(self):
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book", "reservation_confirm")
        self._login(self.actor)
        self.client.post(self._lifecycle(reservation), {"action": "confirm"})
        reservation.refresh_from_db()
        self.assertEqual(reservation.reservation_status, ReservationStatus.CONFIRMED)

    def test_a_missing_permission_is_a_403(self):
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book")  # no confirm
        self._login(self.actor)
        response = self.client.post(self._lifecycle(reservation), {"action": "confirm"})
        self.assertEqual(response.status_code, 403)

    def test_a_state_failure_is_a_message_not_a_403(self):
        """An illegal transition means "not yet", not "not you" — answering it
        with a 403 dead-ends a user whose tab merely went stale."""
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book", "reservation_confirm")
        self._login(self.actor)
        self.client.post(self._lifecycle(reservation), {"action": "confirm"})
        response = self.client.post(
            self._lifecycle(reservation), {"action": "confirm"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(m.tags == "error" for m in response.context["messages"]),
            "a repeated transition should surface as an error message",
        )

    def test_the_lifecycle_card_renders_only_for_a_confirmer(self):
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book")
        self._login(self.actor)
        detail = reverse("dispatching_reservation_detail", kwargs={"pk": reservation.pk})
        self.assertFalse(self.client.get(detail).context["show_lifecycle"])

        self._grant(self.actor, "reservation_confirm")
        self._login(self.actor)
        self.assertTrue(self.client.get(detail).context["show_lifecycle"])


class HandoverRouteTests(ReservationViewTestCase):
    """One page per handover step. The dispatcher track makes meters official;
    the user track does not."""

    def _confirm(self, reservation):
        self.client.post(
            reverse("dispatching_reservation_lifecycle", kwargs={"pk": reservation.pk}),
            {"action": "confirm"},
        )

    def test_each_handover_page_renders(self):
        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS)
        self._login(self.actor)
        for name in (
            "dispatching_reservation_user_checkout",
            "dispatching_reservation_user_checkin",
            "dispatching_reservation_dispatcher_checkout",
            "dispatching_reservation_dispatcher_checkin",
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, kwargs={"pk": reservation.pk}))
                self.assertEqual(response.status_code, 200)
                self.assertIn("activity_card", response.context)

    def test_a_handover_page_refuses_without_its_permission(self):
        reservation = self._make_reservation()
        self._grant(self.actor, "reservation_book")
        self._login(self.actor)
        for name in (
            "dispatching_reservation_user_checkout",
            "dispatching_reservation_dispatcher_checkout",
        ):
            with self.subTest(route=name):
                response = self.client.get(reverse(name, kwargs={"pk": reservation.pk}))
                self.assertEqual(response.status_code, 403)

    def test_user_meters_are_stored_but_never_become_official(self):
        from app.assets.models import MeterHistory

        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS)
        self._login(self.actor)
        self._confirm(reservation)

        before = MeterHistory.objects.filter(asset_id=reservation.asset_id).count()
        asset_meter1 = reservation.asset.meter1

        self.client.post(
            reverse("dispatching_reservation_user_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good", "notes": "n", "meter1": "1234.5", "meter2": "67"},
        )
        reservation.refresh_from_db()
        reservation.asset.refresh_from_db()

        self.assertEqual(reservation.user_meter1_out, 1234.5)
        self.assertEqual(reservation.user_meter2_out, 67)
        self.assertEqual(
            MeterHistory.objects.filter(asset_id=reservation.asset_id).count(), before,
            "the user track must not write meter history",
        )
        self.assertEqual(
            reservation.asset.meter1, asset_meter1,
            "the user track must not move the asset's own reading",
        )
        self.assertIsNone(reservation.initial_meter_read_id)

    def test_dispatcher_meters_are_an_official_asset_update(self):
        from app.assets.models import MeterHistory

        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS)
        self._login(self.actor)
        self._confirm(reservation)

        self.client.post(
            reverse("dispatching_reservation_dispatcher_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good", "meter1": "5000", "meter2": "120"},
        )
        reservation.refresh_from_db()
        reservation.asset.refresh_from_db()

        self.assertEqual(reservation.reservation_status, ReservationStatus.CHECKED_OUT)
        self.assertEqual(reservation.asset.meter1, 5000)
        self.assertEqual(reservation.asset.meter2, 120)
        written = MeterHistory.objects.filter(
            asset_id=reservation.asset_id, source="dispatching_checkout"
        )
        self.assertEqual(written.count(), 2, "both meters should be recorded")
        # The FK points at the lowest-indexed reading of the batch.
        self.assertEqual(reservation.initial_meter_read.meter_index, 1)

    def test_the_verifier_may_not_be_the_self_service_actor(self):
        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS)
        self._login(self.actor)
        self._confirm(reservation)
        self.client.post(
            reverse("dispatching_reservation_user_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good"},
        )
        response = self.client.post(
            reverse("dispatching_reservation_dispatcher_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good"}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(
            reservation.reservation_status,
            ReservationStatus.USER_CHECKED_OUT,
            "the same person must not be able to verify their own self-service entry",
        )

    def test_a_dispatch_manager_may_record_the_user_track_on_someones_behalf(self):
        reservation = self._make_reservation(accountable=self.other_user)
        self._grant(self.actor, *RESERVATION_PERMS, "template_commit")
        self._login(self.actor)
        self._confirm(reservation)
        self.client.post(
            reverse("dispatching_reservation_user_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good"},
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.reservation_status, ReservationStatus.USER_CHECKED_OUT)
        self.assertEqual(reservation.user_checked_out_by_id, self.actor.pk)

    def test_a_plain_holder_may_not_record_someone_elses_user_track(self):
        reservation = self._make_reservation(accountable=self.other_user)
        self._grant(self.actor, *RESERVATION_PERMS)  # no template_commit
        self._login(self.actor)
        self._confirm(reservation)
        response = self.client.post(
            reverse("dispatching_reservation_user_checkout", kwargs={"pk": reservation.pk}),
            {"condition": "good"}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.reservation_status, ReservationStatus.CONFIRMED)


class ReservationEditTests(ReservationViewTestCase):
    def test_edit_writes_fields_but_never_status(self):
        reservation = self._make_reservation()
        self._grant(self.actor, *RESERVATION_PERMS, "template_commit")
        self._login(self.actor)
        response = self.client.post(
            reverse("dispatching_reservation_edit", kwargs={"pk": reservation.pk}),
            {
                "title": "Renamed", "description": "d",
                "reservation_type": ReservationType.RENTAL,
                "asset_id": reservation.asset_id,
                "accountable_person_id": reservation.accountable_person_id,
                "domain_id": reservation.domain_id,
                "scheduled_start": timezone.localtime(reservation.scheduled_start).strftime("%Y-%m-%dT%H:%M"),
                "scheduled_end": timezone.localtime(reservation.scheduled_end).strftime("%Y-%m-%dT%H:%M"),
                "origin": "A", "destination": "B",
                # Status is deliberately not a field on this form; sending one
                # anyway must have no effect.
                "reservation_status": ReservationStatus.RETURNED,
            },
        )
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.title, "Renamed")
        self.assertEqual(reservation.reservation_type, ReservationType.RENTAL)
        self.assertEqual(reservation.origin, "A")
        self.assertEqual(reservation.reservation_status, ReservationStatus.TENTATIVE)

    def test_edit_refuses_an_inverted_window(self):
        reservation = self._make_reservation()
        original_title = reservation.title
        self._grant(self.actor, *RESERVATION_PERMS, "template_commit")
        self._login(self.actor)
        response = self.client.post(
            reverse("dispatching_reservation_edit", kwargs={"pk": reservation.pk}),
            {
                "title": "Should not stick", "reservation_type": ReservationType.WORK,
                "asset_id": reservation.asset_id,
                "accountable_person_id": reservation.accountable_person_id,
                "domain_id": reservation.domain_id,
                "scheduled_start": timezone.localtime(reservation.scheduled_end + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
                "scheduled_end": timezone.localtime(reservation.scheduled_start).strftime("%Y-%m-%dT%H:%M"),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.title, original_title)
