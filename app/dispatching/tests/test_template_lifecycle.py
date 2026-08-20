"""Template lifecycle: session-held draft -> commit produces exactly one
revision however many edits it contains (D4, R3, R4); a commit against a
stale head is refused (R6); instantiation copies and the dispatch deviates
independently (§7)."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

from app.dispatching.control_layer.adapters.template_draft_session_adapter import (
    TemplateDraftSessionAdapter,
)
from app.dispatching.control_layer.factories.dispatch_from_template_factory import (
    DispatchFromTemplateFactory,
)
from app.dispatching.control_layer.template_context import TemplateContext
from app.dispatching.models.templates.dispatch_template_revision import (
    DispatchTemplateRevision,
)
from app.dispatching.tests.base import DispatchingTestCase


class _FakeSessionRequest:
    def __init__(self) -> None:
        self.session = SessionStore()


class TemplateDraftCommitTestCase(DispatchingTestCase):
    def test_several_edits_in_one_session_produce_exactly_one_revision(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", asset_class_id=self.asset_class.pk)
        adapter.add_requirement(kind="capability", capability_definition_id=self.capability.pk, is_required=True)
        adapter.add_requirement(
            kind="skill", skill_id=self.skill.pk, is_required=True, quantity=2, minimum_level=3,
        )
        adapter.add_material_requirement(part_id=self.part.pk, quantity=100, notes="wire")
        adapter.set_metadata(change_note="Initial standard.")

        before = DispatchTemplateRevision.objects.count()
        revision = adapter.commit(actor=self.actor)
        after = DispatchTemplateRevision.objects.count()

        self.assertEqual(after - before, 1)
        self.assertEqual(revision.revision_number, 1)
        self.assertEqual(revision.requested_capabilities.count(), 1)
        self.assertEqual(revision.requested_skills.count(), 1)
        self.assertEqual(revision.material_requirements.count(), 1)

    def test_commit_requires_a_change_note(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="No change note")
        with self.assertRaises(ValueError):
            adapter.commit(actor=self.actor)

    def test_discarding_a_draft_writes_nothing(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Abandoned draft")
        adapter.add_requirement(kind="capability", capability_definition_id=self.capability.pk)

        before = DispatchTemplateRevision.objects.count()
        adapter.clear()
        after = DispatchTemplateRevision.objects.count()
        self.assertEqual(before, after)

    def test_head_moves_and_prior_revision_is_superseded(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", change_note="v1")
        revision_1 = adapter.commit(actor=self.actor)
        template = revision_1.template

        adapter_2 = TemplateDraftSessionAdapter.start_edit(request, template_id=template.pk)
        adapter_2.set_metadata(change_note="v2 improvement")
        revision_2 = adapter_2.commit(actor=self.actor)

        template.refresh_from_db()
        self.assertEqual(template.head_revision_id, revision_2.pk)
        self.assertEqual(revision_2.prior_revision_id, revision_1.pk)
        # Revision 1 is still readable, untouched.
        revision_1.refresh_from_db()
        self.assertEqual(revision_1.title, "Site survey")

    def test_stale_commit_is_refused_naming_the_newer_revision(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", change_note="v1")
        revision_1 = adapter.commit(actor=self.actor)
        template = revision_1.template

        # Two managers open the editor concurrently on revision 1.
        adapter_a = TemplateDraftSessionAdapter.start_edit(request, template_id=template.pk)
        adapter_a.set_metadata(change_note="from manager A")

        # Manager B commits first.
        adapter_b = TemplateDraftSessionAdapter.start_edit(_FakeSessionRequest(), template_id=template.pk)
        adapter_b.set_metadata(change_note="from manager B")
        revision_2 = adapter_b.commit(actor=self.other_user)

        # Manager A's commit is now stale.
        with self.assertRaises(ValueError) as ctx:
            adapter_a.commit(actor=self.actor)
        self.assertIn(str(revision_2.pk), str(ctx.exception))

    def test_copy_to_new_template_creates_an_independent_lineage(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", change_note="v1")
        adapter.add_requirement(kind="capability", capability_definition_id=self.capability.pk)
        revision_1 = adapter.commit(actor=self.actor)
        source_template = revision_1.template

        copy_adapter = TemplateDraftSessionAdapter.start_copy(request, template_id=source_template.pk)
        copy_adapter.set_metadata(title="Site survey, winter", change_note="Seeded from Site survey")
        new_revision = copy_adapter.commit(actor=self.actor)

        self.assertNotEqual(new_revision.template_id, source_template.pk)
        self.assertEqual(new_revision.revision_number, 1)
        self.assertEqual(new_revision.template.copied_from_revision_id, revision_1.pk)
        self.assertEqual(new_revision.requested_capabilities.count(), 1)

        # Improving the original never touches the copy.
        adapter_2 = TemplateDraftSessionAdapter.start_edit(_FakeSessionRequest(), template_id=source_template.pk)
        adapter_2.set_metadata(change_note="Improve original")
        adapter_2.commit(actor=self.actor)
        new_revision.template.refresh_from_db()
        self.assertEqual(new_revision.template.head_revision_id, new_revision.pk)


class TemplateRetirementTestCase(DispatchingTestCase):
    def test_retire_requires_a_reason(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", change_note="v1")
        revision = adapter.commit(actor=self.actor)
        ctx = TemplateContext(revision.template_id, self.actor)
        with self.assertRaises(ValueError):
            ctx.retire(reason="")

    def test_retire_then_reinstate(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(title="Site survey", change_note="v1")
        revision = adapter.commit(actor=self.actor)
        ctx = TemplateContext(revision.template_id, self.actor)

        ctx.retire(reason="No longer run this survey.")
        self.assertTrue(ctx.template.is_retired)

        ctx.reinstate()
        self.assertFalse(ctx.template.is_retired)


class DispatchFromTemplateFactoryTestCase(DispatchingTestCase):
    def _committed_template(self):
        request = _FakeSessionRequest()
        adapter = TemplateDraftSessionAdapter.start_new(request, domain_id=self.domain.pk)
        adapter.set_metadata(
            title="Site survey", asset_class_id=self.asset_class.pk, dispatch_scope="local",
            change_note="Initial standard.",
        )
        adapter.add_requirement(kind="capability", capability_definition_id=self.capability.pk, is_required=True)
        adapter.add_material_requirement(part_id=self.part.pk, quantity=100, notes="wire")
        return adapter.commit(actor=self.actor)

    def test_instantiation_copies_manifest_and_records_source_revision(self):
        revision = self._committed_template()
        start = timezone.now() + timedelta(days=4)
        end = start + timedelta(hours=3)

        dispatch = DispatchFromTemplateFactory.instantiate(
            template_id=revision.template_id, requested_for_id=self.actor.pk,
            desired_start=start, desired_end=end, actor=self.actor,
        )

        self.assertEqual(dispatch.created_from_revision_id, revision.pk)
        self.assertEqual(dispatch.requested_capabilities.count(), 1)
        self.assertEqual(dispatch.demand_links.count(), 1)
        self.assertEqual(dispatch.asset_class_id, self.asset_class.pk)
        self.assertEqual(dispatch.dispatch_scope, "local")

    def test_editing_the_template_afterwards_never_touches_the_raised_dispatch(self):
        revision = self._committed_template()
        start = timezone.now() + timedelta(days=4)
        end = start + timedelta(hours=3)
        dispatch = DispatchFromTemplateFactory.instantiate(
            template_id=revision.template_id, requested_for_id=self.actor.pk,
            desired_start=start, desired_end=end, actor=self.actor,
        )

        adapter = TemplateDraftSessionAdapter.start_edit(_FakeSessionRequest(), template_id=revision.template_id)
        adapter.remove_requirement(kind="capability", temp_id=adapter.draft["requirements"]["capability"][0]["temp_id"])
        adapter.set_metadata(change_note="Dropped the capability requirement.")
        adapter.commit(actor=self.actor)

        dispatch.refresh_from_db()
        self.assertEqual(dispatch.requested_capabilities.count(), 1)
        self.assertEqual(dispatch.created_from_revision_id, revision.pk)

    def test_retired_template_cannot_be_instantiated(self):
        revision = self._committed_template()
        TemplateContext(revision.template_id, self.actor).retire(reason="stopped running this job")
        with self.assertRaises(ValueError):
            DispatchFromTemplateFactory.instantiate(
                template_id=revision.template_id, requested_for_id=self.actor.pk,
                desired_start=timezone.now(), desired_end=timezone.now() + timedelta(hours=1),
                actor=self.actor,
            )
