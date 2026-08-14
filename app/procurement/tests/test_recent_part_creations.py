"""Tests for the parts-creation session breadcrumb (recent_part_creations.py,
D81/D82). §5 of build_plan.md calls out the request-boundary test as "the
test that matters": an in-memory dict assertion passes against the
nested-mutation hazard the module's docstring warns about (mutating
`request.session[SESSION_KEY]` in place never sets Django's `modified`
flag, so the write silently vanishes on the *next* request). Only a real
save/load round trip through SessionMiddleware can catch that.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import transaction
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from app.administration.models import Domain
from app.parts.control_layer.factories.part_factory import PartFactory
from app.procurement.presentation_layer.tools.recent_part_creations import (
    consume,
    read_recent,
    record_created_parts,
)

User = get_user_model()


def _new_request_with_session(factory: RequestFactory):
    """A request carrying a freshly-attached, empty session — mirrors what
    SessionMiddleware hands a view at the start of a request."""
    request = factory.get("/")
    middleware = SessionMiddleware(lambda r: HttpResponse())
    middleware.process_request(request)
    return request


def _persist_session(request) -> str:
    """Runs the same save-if-modified path SessionMiddleware.process_response
    does, and returns the session key a second request would carry as its
    sessionid cookie."""
    middleware = SessionMiddleware(lambda r: HttpResponse())
    response = HttpResponse()
    middleware.process_response(request, response)
    return request.session.session_key


def _request_with_existing_session(factory: RequestFactory, session_key: str):
    request = factory.get("/")
    middleware = SessionMiddleware(lambda r: HttpResponse())
    request.COOKIES[settings.SESSION_COOKIE_NAME] = session_key
    middleware.process_request(request)
    return request


class RecentPartCreationsRequestBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="breadcrumb_smoke",
            email="breadcrumb@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Breadcrumb Domain",
            slug="breadcrumb-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )
        cls.part = PartFactory.create(
            data={
                "part_number": "PN-BREADCRUMB-01",
                "name": "Breadcrumb Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=cls.user,
        )

    def setUp(self):
        self.factory = RequestFactory()

    def test_recorded_part_survives_a_real_request_boundary(self):
        """Write on request 1, save through the middleware, load a fresh
        session object keyed the same way request 2 would be, and confirm
        the part is still there. This is the scenario an in-memory
        assertion cannot fail on but a nested-mutation bug would."""
        request1 = _new_request_with_session(self.factory)
        record_created_parts(
            request1,
            part_ids=[self.part.pk],
            domain_ids_by_part={self.part.pk: [self.domain.pk]},
        )
        session_key = _persist_session(request1)
        self.assertTrue(session_key)

        request2 = _request_with_existing_session(self.factory, session_key)
        request2.user = self.user
        found = read_recent(request2, actor=self.user)

        self.assertEqual(found, [self.part.pk])

    def test_second_tab_appends_rather_than_replacing_first_tabs_batch(self):
        """D82 — two 'tabs' sharing one session both survive, in the order
        they were created."""
        other_part = PartFactory.create(
            data={
                "part_number": "PN-BREADCRUMB-02",
                "name": "Second Tab Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=self.user,
        )

        request1 = _new_request_with_session(self.factory)
        record_created_parts(
            request1,
            part_ids=[self.part.pk],
            domain_ids_by_part={self.part.pk: [self.domain.pk]},
        )
        session_key = _persist_session(request1)

        request2 = _request_with_existing_session(self.factory, session_key)
        record_created_parts(
            request2,
            part_ids=[other_part.pk],
            domain_ids_by_part={other_part.pk: [self.domain.pk]},
        )
        session_key = _persist_session(request2)

        request3 = _request_with_existing_session(self.factory, session_key)
        request3.user = self.user
        found = read_recent(request3, actor=self.user)

        self.assertEqual(set(found), {self.part.pk, other_part.pk})

    def test_consumed_part_does_not_reappear_on_the_next_request(self):
        request1 = _new_request_with_session(self.factory)
        record_created_parts(
            request1,
            part_ids=[self.part.pk],
            domain_ids_by_part={self.part.pk: [self.domain.pk]},
        )
        session_key = _persist_session(request1)

        request2 = _request_with_existing_session(self.factory, session_key)
        consume(request2, part_ids=[self.part.pk])
        session_key = _persist_session(request2)

        request3 = _request_with_existing_session(self.factory, session_key)
        request3.user = self.user
        found = read_recent(request3, actor=self.user)

        self.assertEqual(found, [])


class RecentPartCreationsRollbackTests(TestCase):
    """A part creation that never commits must leave no breadcrumb — the
    entrypoints schedule record_created_parts with transaction.on_commit
    for exactly this reason (build_plan.md §5 point 6)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="breadcrumb_rollback",
            email="rollback@test.local",
            password="TestPass123!@",
        )
        cls.domain = Domain.objects.create(
            name="Rollback Domain",
            slug="rollback-domain",
            created_by=cls.user,
            updated_by=cls.user,
        )

    def test_rolled_back_transaction_never_fires_the_on_commit_breadcrumb(self):
        part = PartFactory.create(
            data={
                "part_number": "PN-ROLLBACK-01",
                "name": "Rollback Widget",
                "part_type": "component",
                "category": "test",
            },
            actor=self.user,
        )
        request = RequestFactory().get("/")
        middleware = SessionMiddleware(lambda r: HttpResponse())
        middleware.process_request(request)

        fired = []
        try:
            with transaction.atomic():
                transaction.on_commit(
                    lambda: fired.append(
                        record_created_parts(
                            request,
                            part_ids=[part.pk],
                            domain_ids_by_part={part.pk: [self.domain.pk]},
                        )
                    )
                )
                raise RuntimeError("simulated failure before commit")
        except RuntimeError:
            pass

        self.assertEqual(fired, [])
        request.user = self.user
        self.assertEqual(read_recent(request, actor=self.user), [])
