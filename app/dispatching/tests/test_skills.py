"""Skills: SkillCertificationValidator (one record per person per skill) and
UserSkillManager.certify/update/revoke."""

from __future__ import annotations

import datetime

from app.dispatching.control_layer.guards.skill_certification_guard import (
    SkillCertificationValidator,
)
from app.dispatching.control_layer.managers.dispatch_skill_manager import (
    DispatchSkillManager,
)
from app.dispatching.control_layer.managers.user_skill_manager import (
    UserSkillManager,
    UserSkillValidationError,
)
from app.dispatching.tests.base import DispatchingTestCase


class SkillCertificationValidatorTestCase(DispatchingTestCase):
    def test_valid_certification_passes(self):
        errors = SkillCertificationValidator.check(
            user_id=self.actor.pk, skill_id=self.skill.pk, level=3,
        )
        self.assertEqual(errors, [])

    def test_level_out_of_range_is_rejected(self):
        errors = SkillCertificationValidator.check(
            user_id=self.actor.pk, skill_id=self.skill.pk, level=9,
        )
        self.assertTrue(errors)

    def test_duplicate_certification_is_rejected(self):
        UserSkillManager.certify(data={"user_id": self.actor.pk, "skill_id": self.skill.pk, "level": 2}, actor=self.actor)
        errors = SkillCertificationValidator.check(user_id=self.actor.pk, skill_id=self.skill.pk, level=3)
        self.assertTrue(errors)

    def test_inactive_skill_is_rejected(self):
        DispatchSkillManager.deactivate(skill_id=self.skill.pk, actor=self.actor)
        errors = SkillCertificationValidator.check(user_id=self.actor.pk, skill_id=self.skill.pk, level=1)
        self.assertTrue(errors)

    def test_expiry_required_when_skill_demands_it(self):
        self.skill.requires_expiry = True
        self.skill.save(update_fields=["requires_expiry"])
        errors = SkillCertificationValidator.check(user_id=self.actor.pk, skill_id=self.skill.pk, level=1)
        self.assertTrue(errors)

    def test_expiry_before_certification_is_rejected(self):
        errors = SkillCertificationValidator.check(
            user_id=self.actor.pk, skill_id=self.skill.pk, level=1,
            certified_at=datetime.date(2026, 6, 1), expires_at=datetime.date(2026, 1, 1),
        )
        self.assertTrue(errors)


class UserSkillManagerTestCase(DispatchingTestCase):
    def test_certify_creates_a_record(self):
        certification = UserSkillManager.certify(
            data={"user_id": self.actor.pk, "skill_id": self.skill.pk, "level": 4}, actor=self.actor,
        )
        self.assertTrue(certification.is_active)
        self.assertEqual(certification.level, 4)

    def test_certify_twice_is_refused(self):
        UserSkillManager.certify(data={"user_id": self.actor.pk, "skill_id": self.skill.pk}, actor=self.actor)
        with self.assertRaises(UserSkillValidationError):
            UserSkillManager.certify(data={"user_id": self.actor.pk, "skill_id": self.skill.pk}, actor=self.actor)

    def test_revoke_flips_is_active_and_frees_recertification(self):
        certification = UserSkillManager.certify(
            data={"user_id": self.actor.pk, "skill_id": self.skill.pk}, actor=self.actor,
        )
        UserSkillManager.revoke(user_skill_id=certification.pk, actor=self.actor)
        certification.refresh_from_db()
        self.assertFalse(certification.is_active)

        # Recertification reuses the row rather than fighting the unique constraint.
        updated = UserSkillManager.update(
            user_skill_id=certification.pk, data={"level": 5}, actor=self.actor,
        )
        self.assertEqual(updated.level, 5)
