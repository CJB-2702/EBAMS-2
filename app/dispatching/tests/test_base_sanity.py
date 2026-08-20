from __future__ import annotations

from app.dispatching.tests.base import DispatchingTestCase


class BaseFixtureSanityTestCase(DispatchingTestCase):
    def test_fixture_objects_exist(self):
        self.assertTrue(self.actor.pk)
        self.assertTrue(self.domain.pk)
        self.assertTrue(self.asset.pk)
        self.assertTrue(self.asset_2.pk)
        self.assertTrue(self.capability.pk)
        self.assertTrue(self.skill.pk)
        self.assertTrue(self.part.pk)
