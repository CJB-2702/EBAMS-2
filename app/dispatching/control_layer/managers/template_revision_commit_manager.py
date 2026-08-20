"""Manager: TemplateRevisionCommitManager — the one path that writes a
template draft to the database. One transaction creates the revision plus
its whole requirement manifest, moves the head, and (for a revision of an
existing lineage) implicitly supersedes the previous head — all in a single
atomic block, however many edits the draft accumulated
(dispatching_starter_kit/1_dispatch_templates.md §3.2, R3, R4)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.template_head_drift_guard import (
    TemplateHeadDriftPolicy,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

_REQUIREMENT_MODELS = {
    "capability": ("app.dispatching.models.templates.template_requested_capability", "DispatchTemplateRequestedCapability", "capability_definition_id"),
    "skill": ("app.dispatching.models.templates.template_requested_skill", "DispatchTemplateRequestedSkill", "skill_id"),
    "model": ("app.dispatching.models.templates.template_requested_model", "DispatchTemplateRequestedModel", "model_id"),
    "modification": ("app.dispatching.models.templates.template_requested_modification", "DispatchTemplateRequestedModification", "defined_modification_id"),
}


def _import_model(module_path: str, class_name: str):
    import importlib

    return getattr(importlib.import_module(module_path), class_name)


class TemplateRevisionCommitManager:
    @classmethod
    def commit_draft(cls, *, draft: dict, actor: "AbstractUser"):
        if not (draft.get("title") or "").strip():
            raise ValueError("A title is required to commit a revision.")
        if not (draft.get("change_note") or "").strip():
            raise ValueError("A change note is required to commit a revision.")
        if not draft.get("domain_id"):
            raise ValueError("A domain is required to commit a revision.")

        from app.dispatching.models.templates.dispatch_template import DispatchTemplate
        from app.dispatching.models.templates.dispatch_template_revision import (
            DispatchTemplateRevision,
        )
        from app.dispatching.models.templates.template_material_requirement import (
            DispatchTemplateMaterialRequirement,
        )

        with transaction.atomic():
            template_id = draft.get("template_id")
            if template_id:
                template = DispatchTemplate.objects.select_for_update().get(pk=template_id)
                TemplateHeadDriftPolicy.check(
                    template=template, draft_prior_revision_id=draft.get("prior_revision_id")
                )
                revision_number = (
                    DispatchTemplateRevision.objects.filter(template=template).count() + 1
                )
                prior_revision_id = template.head_revision_id
            else:
                template = DispatchTemplate.objects.create(
                    domain_id=draft["domain_id"],
                    copied_from_revision_id=draft.get("copied_from_revision_id"),
                    created_by=actor,
                    updated_by=actor,
                )
                revision_number = 1
                prior_revision_id = None

            revision = DispatchTemplateRevision.objects.create(
                template=template,
                revision_number=revision_number,
                title=draft["title"],
                asset_class_id=draft.get("asset_class_id"),
                asset_subclass_text=draft.get("asset_subclass_text", ""),
                dispatch_scope=draft.get("dispatch_scope", ""),
                activity_location=draft.get("activity_location", ""),
                estimated_meter_usage=draft.get("estimated_meter_usage"),
                headcount=draft.get("headcount"),
                notes=draft.get("notes", ""),
                change_note=draft["change_note"],
                prior_revision_id=prior_revision_id,
                created_by=actor,
                updated_by=actor,
            )

            for kind, rows in draft.get("requirements", {}).items():
                module_path, class_name, target_field = _REQUIREMENT_MODELS[kind]
                model = _import_model(module_path, class_name)
                for row in rows:
                    create_kwargs = {
                        "revision": revision,
                        target_field: row[target_field],
                        "is_required": row.get("is_required", True),
                        "notes": row.get("notes", ""),
                        "created_by": actor,
                        "updated_by": actor,
                    }
                    if kind in ("skill", "model") and "quantity" in row:
                        create_kwargs["quantity"] = row["quantity"]
                    if kind == "skill" and "minimum_level" in row:
                        create_kwargs["minimum_level"] = row["minimum_level"]
                    if kind == "model" and row.get("configuration_template_id"):
                        create_kwargs["configuration_template_id"] = row["configuration_template_id"]
                    model.objects.create(**create_kwargs)

            for material in draft.get("material_requirements", []):
                DispatchTemplateMaterialRequirement.objects.create(
                    revision=revision,
                    part_id=material["part_id"],
                    quantity=material["quantity"],
                    notes=material.get("notes", ""),
                    created_by=actor,
                    updated_by=actor,
                )

            template.head_revision = revision
            template.updated_by = actor
            template.save(update_fields=["head_revision", "updated_by", "updated_at"])

        return revision
