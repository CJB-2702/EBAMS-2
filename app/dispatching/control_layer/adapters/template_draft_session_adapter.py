"""Adapter: TemplateDraftSessionAdapter — the working draft lives in
request.session['dispatch_template_draft']. Every method except commit()
only mutates the session dict; there are no draft rows in the database (D4,
dispatching_starter_kit/1_dispatch_templates.md §3.2). commit() is the one
path that touches the database, via TemplateRevisionCommitManager, inside a
single atomic transaction — four edits produce exactly one revision.

Follows app/maintenance/control_layer/adapters/template_builder_session_adapter.py,
the established pattern for this kind of session-held multi-card draft.
"""

from __future__ import annotations

import uuid

SESSION_KEY = "dispatch_template_draft"

_REQUIREMENT_KINDS = ("capability", "skill", "model", "modification")


def _blank_draft() -> dict:
    return {
        "template_id": None,
        "domain_id": None,
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
        "requirements": {kind: [] for kind in _REQUIREMENT_KINDS},
        "material_requirements": [],
    }


def _requirement_row_from(row) -> dict:
    out = {
        "temp_id": uuid.uuid4().hex,
        "is_required": row.is_required,
        "notes": row.notes,
    }
    if hasattr(row, "capability_definition_id"):
        out["capability_definition_id"] = row.capability_definition_id
    if hasattr(row, "skill_id"):
        out["skill_id"] = row.skill_id
        out["quantity"] = row.quantity
        out["minimum_level"] = row.minimum_level
    if hasattr(row, "model_id"):
        out["model_id"] = row.model_id
        out["quantity"] = row.quantity
    if hasattr(row, "defined_modification_id"):
        out["defined_modification_id"] = row.defined_modification_id
    if hasattr(row, "configuration_template_id"):
        out["configuration_template_id"] = row.configuration_template_id
    return out


class TemplateDraftSessionAdapter:
    def __init__(self, request) -> None:
        self._request = request
        if SESSION_KEY not in request.session:
            request.session[SESSION_KEY] = _blank_draft()

    @classmethod
    def start_new(cls, request, *, domain_id: int) -> "TemplateDraftSessionAdapter":
        draft = _blank_draft()
        draft["domain_id"] = domain_id
        request.session[SESSION_KEY] = draft
        request.session.modified = True
        return cls(request)

    @classmethod
    def _seed_from_head(cls, request, *, template_id: int) -> tuple["TemplateDraftSessionAdapter", object]:
        from app.dispatching.models.templates.dispatch_template import DispatchTemplate

        template = DispatchTemplate.objects.select_related("head_revision").get(pk=template_id)
        head = template.head_revision
        if head is None:
            raise ValueError(f"Template #{template_id} has no head revision to edit from.")

        draft = _blank_draft()
        draft["domain_id"] = template.domain_id
        draft["title"] = head.title
        draft["asset_class_id"] = head.asset_class_id
        draft["asset_subclass_text"] = head.asset_subclass_text
        draft["dispatch_scope"] = head.dispatch_scope
        draft["activity_location"] = head.activity_location
        draft["estimated_meter_usage"] = head.estimated_meter_usage
        draft["headcount"] = head.headcount
        draft["notes"] = head.notes

        for kind in _REQUIREMENT_KINDS:
            related_name = {
                "capability": "requested_capabilities",
                "skill": "requested_skills",
                "model": "requested_models",
                "modification": "requested_modifications",
            }[kind]
            draft["requirements"][kind] = [
                _requirement_row_from(row) for row in getattr(head, related_name).all()
            ]
        draft["material_requirements"] = [
            {
                "temp_id": uuid.uuid4().hex,
                "part_id": m.part_id,
                "quantity": float(m.quantity),
                "notes": m.notes,
            }
            for m in head.material_requirements.all()
        ]

        request.session[SESSION_KEY] = draft
        request.session.modified = True
        return cls(request), template

    @classmethod
    def start_edit(cls, request, *, template_id: int) -> "TemplateDraftSessionAdapter":
        """A new revision of an existing lineage — a draft always starts from
        the head (§3.5); editing an older revision is start_copy()'s job."""
        adapter, template = cls._seed_from_head(request, template_id=template_id)
        adapter.draft["template_id"] = template.pk
        adapter.draft["prior_revision_id"] = template.head_revision_id
        adapter._save()
        return adapter

    @classmethod
    def start_copy(cls, request, *, template_id: int) -> "TemplateDraftSessionAdapter":
        """Seeds a draft from a source revision into what will become a
        NEW, unrelated lineage — provenance recorded, no ongoing dependency
        (doc 1 §4)."""
        adapter, template = cls._seed_from_head(request, template_id=template_id)
        adapter.draft["template_id"] = None
        adapter.draft["prior_revision_id"] = None
        adapter.draft["copied_from_revision_id"] = template.head_revision_id
        adapter._save()
        return adapter

    @property
    def draft(self) -> dict:
        return self._request.session[SESSION_KEY]

    def _save(self) -> None:
        self._request.session.modified = True

    def clear(self) -> None:
        self._request.session.pop(SESSION_KEY, None)

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def set_metadata(self, **fields) -> None:
        for key, value in fields.items():
            if key in self.draft:
                self.draft[key] = value
        self._save()

    # ------------------------------------------------------------------ #
    # Requirements
    # ------------------------------------------------------------------ #

    def add_requirement(self, *, kind: str, **fields) -> dict:
        if kind not in _REQUIREMENT_KINDS:
            raise ValueError(f"Unknown requirement kind '{kind}'.")
        row = {"temp_id": uuid.uuid4().hex, "is_required": fields.get("is_required", True), "notes": fields.get("notes", "")}
        for key in (
            "capability_definition_id", "skill_id", "model_id",
            "defined_modification_id", "configuration_template_id",
            "quantity", "minimum_level",
        ):
            if key in fields:
                row[key] = fields[key]
        self.draft["requirements"][kind].append(row)
        self._save()
        return row

    def remove_requirement(self, *, kind: str, temp_id: str) -> None:
        if kind not in _REQUIREMENT_KINDS:
            raise ValueError(f"Unknown requirement kind '{kind}'.")
        self.draft["requirements"][kind] = [
            r for r in self.draft["requirements"][kind] if r["temp_id"] != temp_id
        ]
        self._save()

    # ------------------------------------------------------------------ #
    # Material requirements
    # ------------------------------------------------------------------ #

    def add_material_requirement(self, *, part_id: int, quantity: float, notes: str = "") -> dict:
        row = {"temp_id": uuid.uuid4().hex, "part_id": part_id, "quantity": quantity, "notes": notes}
        self.draft["material_requirements"].append(row)
        self._save()
        return row

    def remove_material_requirement(self, *, temp_id: str) -> None:
        self.draft["material_requirements"] = [
            m for m in self.draft["material_requirements"] if m["temp_id"] != temp_id
        ]
        self._save()

    # ------------------------------------------------------------------ #
    # Commit — the only path that touches the database
    # ------------------------------------------------------------------ #

    def commit(self, *, actor) -> object:
        from app.dispatching.control_layer.managers.template_revision_commit_manager import (
            TemplateRevisionCommitManager,
        )

        revision = TemplateRevisionCommitManager.commit_draft(draft=self.draft, actor=actor)
        self.clear()
        return revision
