"""seed_dispatching_dev -- dev fixture contribution for the Dispatching
module's Phase 3 UI (build_phase_3_ui.md): the skills catalogue, a couple of
certifications, and dispatch templates with real revision history.

Everything that has a real control-layer entrypoint goes through it, exactly
as production traffic would:

  - Templates are built through TemplateRevisionCommitManager.commit_draft(),
    the same manager the session-backed draft editor calls at commit --
    driven from a plain draft dict here rather than a real HTTP session,
    since the manager only ever reads the dict shape, never the session
    object itself.
  - Certifications go through UserSkillManager.certify().
  - Retirement goes through TemplateContext.retire().

DispatchSkill has no dedicated Factory/Manager for plain catalogue creation
-- its real presentation-layer entrypoint (skill_views.skill_create) creates
it with a direct `.objects.create()` itself, so this seed mirrors that same
direct-create shape rather than inventing a control-layer indirection that
doesn't exist in production code.

Seeds:
  - 3 DispatchSkill catalogue entries (CDL Class A, Radio Operator, Hazmat
    Handling), alongside whatever skills already exist.
  - 2 certifications (generic_admin in CDL Class A, generic_manager in Radio
    Operator).
  - 3 DispatchTemplate lineages:
      - "Forklift -- Standard Delivery": 2 committed revisions, so the
        detail page's revision history and head marker have something to
        show.
      - "Boom Lift -- Regional Aerial Job": 1 revision, exercising the
        model + skill + capability requirement kinds together.
      - "Excavator -- Utility Trench": 1 revision, then retired, so the
        list's "show superseded & retired" toggle and the detail page's
        retired banner have data.

Idempotent: skipped entirely once the marker-tagged skill already exists;
safe to re-run.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from app.administration.models import Domain
from app.assets.models import (
    AssetClass,
    AssetModel,
    CapabilityDefinition,
    ConfigurationTemplate,
    DefinedModification,
)
from app.dispatching.control_layer.managers.template_revision_commit_manager import (
    TemplateRevisionCommitManager,
)
from app.dispatching.control_layer.managers.user_skill_manager import UserSkillManager
from app.dispatching.control_layer.template_context import TemplateContext
from app.dispatching.models.skills.dispatch_skill import DispatchSkill
from app.parts.models import Part

User = get_user_model()

SEED_MARKER = "[seeded by seed_dispatching_dev]"


def _blank_draft(*, domain_id: int) -> dict:
    return {
        "template_id": None,
        "domain_id": domain_id,
        "title": "",
        "asset_class_id": None,
        "asset_subclass_text": "",
        "dispatch_scope": "",
        "activity_location": "",
        "estimated_meter_usage": None,
        "headcount": None,
        "notes": "",
        "prior_revision_id": None,
        "copied_from_revision_id": None,
        "change_note": "",
        "requirements": {
            "capability": [], "skill": [], "model": [], "modification": [],
        },
        "material_requirements": [],
    }


class Command(BaseCommand):
    help = (
        "Seed dev Dispatching data: skills catalogue, certifications, and "
        "dispatch templates with committed revision history."
    )

    def handle(self, *args, **options):
        actor = User.objects.filter(username="generic_admin").first() or User.objects.first()
        if actor is None:
            self.stdout.write(self.style.WARNING(
                "No user found -- run the dev_users fixture before seed_dispatching_dev."
            ))
            return

        if DispatchSkill.objects.filter(description__icontains=SEED_MARKER).exists():
            self.stdout.write("Dispatching dev seed already present -- skipping.")
            return

        domain = Domain.objects.filter(slug="north-acme-site-a").first() or Domain.objects.first()
        if domain is None:
            self.stdout.write(self.style.WARNING(
                "No Domain found -- run the dev_ownership fixture before seed_dispatching_dev."
            ))
            return

        parts = list(Part.objects.all()[:2])
        if len(parts) < 2:
            self.stdout.write(self.style.WARNING(
                "Fewer than 2 Parts exist -- run seed_parts_dev before seed_dispatching_dev."
            ))
            return

        skills = self._seed_skills(actor=actor)
        self._seed_certifications(actor=actor, skills=skills)
        templates = self._seed_templates(actor=actor, domain=domain, skills=skills, parts=parts)
        self._seed_dispatches(actor=actor, domain=domain)

        self.stdout.write(self.style.SUCCESS("Dispatching dev seed complete."))

    def _seed_skills(self, *, actor) -> dict[str, DispatchSkill]:
        specs = [
            ("CDL Class A", "CDL-A", "Commercial driver's license, class A.", True),
            ("Radio Operator", "RADIO-OP", "Certified to operate site radio equipment.", False),
            ("Hazmat Handling", "HAZMAT", "Certified to handle hazardous materials.", True),
            ("Forklift Certified", "FORKLIFT", "Certified to operate a warehouse forklift.", False),
        ]
        skills: dict[str, DispatchSkill] = {}
        for name, code, description, requires_expiry in specs:
            skill, _ = DispatchSkill.objects.get_or_create(
                name=name,
                defaults={
                    "code": code,
                    "description": f"{description} {SEED_MARKER}",
                    "requires_expiry": requires_expiry,
                    "is_active": True,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            skills[name] = skill
        return skills

    def _seed_certifications(self, *, actor, skills: dict[str, DispatchSkill]) -> None:
        manager = User.objects.filter(username="generic_manager").first()
        UserSkillManager.certify(
            data={
                "user_id": actor.pk,
                "skill_id": skills["CDL Class A"].pk,
                "level": 3,
                "certified_at": "2025-01-15",
                "expires_at": "2027-01-15",
                "certificate_number": "CDL-SEED-001",
            },
            actor=actor,
        )
        if manager is not None:
            UserSkillManager.certify(
                data={
                    "user_id": manager.pk,
                    "skill_id": skills["Radio Operator"].pk,
                    "level": None,
                    "certified_at": "2025-06-01",
                    "expires_at": None,
                    "certificate_number": "",
                },
                actor=actor,
            )

    def _seed_templates(self, *, actor, domain, skills: dict[str, DispatchSkill], parts: list[Part]) -> None:
        forklift_class = AssetClass.objects.filter(name="Forklift").first()
        boom_lift_class = AssetClass.objects.filter(name="Boom Lift").first()
        excavator_class = AssetClass.objects.filter(name="Excavator").first()
        lifting_cap = CapabilityDefinition.objects.filter(name="Lifting").first()
        aerial_cap = CapabilityDefinition.objects.filter(name="Aerial Work").first()
        forklift_build = ConfigurationTemplate.objects.filter(name="Standard Forklift Build").first()
        forklift_model = AssetModel.objects.filter(model_name="8FGCU25").first()
        boom_lift_model = AssetModel.objects.filter(model_name="Z-45").first()
        forklift_certified = skills["Forklift Certified"]

        # ── Template 1: two revisions, so history + head marker have data.
        # Revision 2 also demonstrates a model requirement gaining a
        # configuration template — an attribute of the model row, not a
        # requirement kind of its own (1_dispatch_templates.md §6.4). ──────
        draft = _blank_draft(domain_id=domain.pk)
        draft["title"] = "Forklift — Standard Delivery"
        draft["asset_class_id"] = forklift_class.pk if forklift_class else None
        draft["asset_subclass_text"] = "Warehouse"
        draft["dispatch_scope"] = "on_site"
        draft["activity_location"] = "Site A Yard"
        draft["headcount"] = 1
        draft["notes"] = "Routine forklift positioning job."
        draft["change_note"] = f"Initial template. {SEED_MARKER}"
        if lifting_cap:
            draft["requirements"]["capability"].append({
                "capability_definition_id": lifting_cap.pk, "is_required": True, "notes": "",
            })
        if forklift_certified:
            draft["requirements"]["skill"].append({
                "skill_id": forklift_certified.pk, "quantity": 1, "minimum_level": None,
                "is_required": True, "notes": "",
            })
        if forklift_model:
            draft["requirements"]["model"].append({
                "model_id": forklift_model.pk, "quantity": 1, "is_required": True, "notes": "",
            })
        draft["material_requirements"].append({"part_id": parts[0].pk, "quantity": 2, "notes": "Standard load straps."})
        revision = TemplateRevisionCommitManager.commit_draft(draft=draft, actor=actor)

        if forklift_build and forklift_model:
            draft2 = _blank_draft(domain_id=domain.pk)
            draft2.update(draft)
            draft2["template_id"] = revision.template_id
            draft2["prior_revision_id"] = revision.pk
            draft2["change_note"] = f"Attach standard build configuration to the forklift requirement. {SEED_MARKER}"
            draft2["requirements"]["model"] = [{
                "model_id": forklift_model.pk, "quantity": 1, "is_required": True, "notes": "",
                "configuration_template_id": forklift_build.pk,
            }]
            TemplateRevisionCommitManager.commit_draft(draft=draft2, actor=actor)

        # ── Template 2: capability + skill + model together ────────────────
        draft = _blank_draft(domain_id=domain.pk)
        draft["title"] = "Boom Lift — Regional Aerial Job"
        draft["asset_class_id"] = boom_lift_class.pk if boom_lift_class else None
        draft["asset_subclass_text"] = "Client site"
        draft["dispatch_scope"] = "regional"
        draft["activity_location"] = "Client site"
        draft["headcount"] = 2
        draft["estimated_meter_usage"] = 50.0
        draft["change_note"] = f"Initial template. {SEED_MARKER}"
        if aerial_cap:
            draft["requirements"]["capability"].append({
                "capability_definition_id": aerial_cap.pk, "is_required": True, "notes": "",
            })
        draft["requirements"]["skill"].append({
            "skill_id": skills["CDL Class A"].pk, "quantity": 1, "minimum_level": 2,
            "is_required": True, "notes": "",
        })
        if boom_lift_model:
            draft["requirements"]["model"].append({
                "model_id": boom_lift_model.pk, "quantity": 1, "is_required": True, "notes": "",
            })
        draft["material_requirements"].append({"part_id": parts[1].pk, "quantity": 1, "notes": ""})
        TemplateRevisionCommitManager.commit_draft(draft=draft, actor=actor)

        # ── Template 3: one revision, then retired ──────────────────────────
        draft = _blank_draft(domain_id=domain.pk)
        draft["title"] = "Excavator — Utility Trench"
        draft["asset_class_id"] = excavator_class.pk if excavator_class else None
        draft["dispatch_scope"] = "local"
        draft["headcount"] = 1
        draft["change_note"] = f"Initial template. {SEED_MARKER}"
        revision3 = TemplateRevisionCommitManager.commit_draft(draft=draft, actor=actor)
        TemplateContext(revision3.template_id, actor).retire(
            reason=f"Superseded by contractor-managed excavation service. {SEED_MARKER}"
        )
        return {"t1": revision, "t2": draft, "t3": revision3}

    def _seed_dispatches(self, *, actor, domain) -> None:
        import datetime
        from django.utils import timezone
        from app.dispatching.control_layer.factories.dispatch_factory import DispatchFactory
        from app.events.models.details.dispatching import DispatchingDetail

        if DispatchingDetail.objects.filter(description__icontains=SEED_MARKER).exists():
            return

        forklift_class = AssetClass.objects.filter(name="Forklift").first()
        if forklift_class:
            now = timezone.now()
            DispatchFactory.create(
                domain_id=domain.pk,
                requested_for_id=actor.pk,
                desired_start=now + datetime.timedelta(days=1),
                desired_end=now + datetime.timedelta(days=2),
                asset_class_id=forklift_class.pk,
                asset_subclass_text="Standard Warehouse",
                headcount=2,
                names_free_text="Alice Smith, Bob Jones",
                requested_assets="Forklift #01",
                dispatch_scope="on_site",
                activity_location="Main Depot Yard",
                title="Forklift Transport for Depot Relocation",
                description=f"Relocating pallet racks from Building A to B. {SEED_MARKER}",
                actor=actor,
            )

