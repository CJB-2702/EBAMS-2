"""Adapter: TemplateBuilderSessionAdapter — replaces the legacy SQL-backed
TemplateBuilderMemory / TemplateBuilderAttachmentReference tables with
request.session['template_builder_draft'].

Every method except commit() only mutates the session dict — zero database
writes while a template is being drafted. commit() is the one path that
touches the database, and it does so inside a single atomic transaction that
creates TemplateActionSet + TemplateActionItem + TemplateActionTool +
TemplatePartDemand together, so a template build either fully lands or fully
rolls back (R2's atomic-cascade rule, applied to template authoring too).
"""

from __future__ import annotations

import copy
import uuid

from django.db import transaction

from app.maintenance.models.templates.template_action_item import TemplateActionItem
from app.maintenance.models.templates.template_action_set import TemplateActionSet
from app.maintenance.models.templates.template_action_tool import TemplateActionTool
from app.maintenance.models.templates.template_part_demand import TemplatePartDemand

SESSION_KEY = "template_builder_draft"


def _blank_draft() -> dict:
    return {
        "task_name": "",
        "description": "",
        "asset_class_id": None,
        "asset_model_ids": [],
        "prior_revision_id": None,
        "revision": "0",
        "revision_note": "",
        "actions": [],
    }


def _tool_name(tool_id) -> str:
    """Catalog name for a tool, for display inside the draft. Empty when the
    row is ad-hoc (no catalog id) or the id no longer resolves."""
    if not tool_id:
        return ""
    from app.parts.models.core.tool import Tool

    return Tool.objects.filter(pk=tool_id).values_list("name", flat=True).first() or ""


def _part_label(part_id) -> str:
    if not part_id:
        return ""
    from app.parts.models.core.part import Part

    part = Part.objects.filter(pk=part_id).values("part_number", "name").first()
    if not part:
        return ""
    return f"{part['part_number']} — {part['name']}"


class TemplateBuilderSessionAdapter:
    def __init__(self, request) -> None:
        self._request = request
        if SESSION_KEY not in request.session:
            request.session[SESSION_KEY] = _blank_draft()

    @classmethod
    def start_revision(cls, request, *, template_action_set_id: int) -> "TemplateBuilderSessionAdapter":
        """Seed a fresh draft by copying an existing template — the session
        equivalent of legacy's copy_from_template(is_revision=True)."""
        template = TemplateActionSet.objects.prefetch_related(
            "template_action_items__template_action_tools",
            "template_action_items__template_part_demands",
        ).get(pk=template_action_set_id, deleted_at__isnull=True)

        draft = _blank_draft()
        draft["task_name"] = template.task_name
        draft["description"] = template.description
        draft["asset_class_id"] = template.asset_class_id
        draft["asset_model_ids"] = list(template.asset_models.values_list("id", flat=True))
        draft["prior_revision_id"] = template.pk
        try:
            draft["revision"] = str(int(template.revision or "0") + 1)
        except ValueError:
            draft["revision"] = "1"

        for item in template.template_action_items.filter(deleted_at__isnull=True).order_by(
            "sequence_order"
        ):
            draft["actions"].append(
                {
                    "temp_id": uuid.uuid4().hex,
                    "action_name": item.action_name,
                    "description": item.description,
                    "instructions": item.instructions,
                    "safety_notes": item.safety_notes,
                    "notes": item.notes,
                    "estimated_duration_minutes": item.estimated_duration_minutes,
                    "sequence_order": item.sequence_order,
                    "proto_action_item_id": item.proto_action_item_id,
                    "tools": [
                        {
                            "tool_id": tool.tool_id,
                            "tool_name": tool.tool_name or (tool.tool.name if tool.tool_id else ""),
                            "quantity_required": tool.quantity_required,
                            "specifications": tool.specifications,
                            "notes": tool.notes,
                            "is_required": tool.is_required,
                        }
                        for tool in item.template_action_tools.filter(deleted_at__isnull=True).select_related("tool")
                    ],
                    "part_demands": [
                        {
                            "part_id": demand.part_id,
                            "part_label": str(demand.part) if demand.part_id else "",
                            "quantity_required": float(demand.quantity_required),
                            "notes": demand.notes,
                            "is_optional": demand.is_optional,
                        }
                        for demand in item.template_part_demands.filter(deleted_at__isnull=True).select_related("part")
                    ],
                }
            )

        request.session[SESSION_KEY] = draft
        request.session.modified = True
        return cls(request)

    @classmethod
    def start_copy(cls, request, *, template_action_set_id: int) -> "TemplateBuilderSessionAdapter":
        """Seed a fresh draft by copying an existing template's contents,
        same as start_revision(), but as an independent template — no
        prior_revision chain, no revision bump. A dedicated method rather
        than start_revision() with the lineage fields stripped client-side,
        since that would let a forged POST leave prior_revision_id set."""
        cls.start_revision(request, template_action_set_id=template_action_set_id)
        adapter = cls(request)
        adapter.draft["prior_revision_id"] = None
        adapter.draft["revision"] = "1"
        adapter.draft["revision_note"] = ""
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
        if "asset_class_id" in fields and fields["asset_class_id"] != self.draft["asset_class_id"]:
            # Assigned models are scoped to the old class — switching class
            # invalidates them rather than leaving cross-class stragglers.
            self.draft["asset_model_ids"] = []
        for key, value in fields.items():
            if key in self.draft:
                self.draft[key] = value
        self._save()

    def add_asset_models(self, model_ids) -> None:
        existing = set(self.draft["asset_model_ids"])
        existing.update(model_ids)
        self.draft["asset_model_ids"] = sorted(existing)
        self._save()

    def remove_asset_models(self, model_ids) -> None:
        removed = set(model_ids)
        self.draft["asset_model_ids"] = [
            pk for pk in self.draft["asset_model_ids"] if pk not in removed
        ]
        self._save()

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def add_action(self, **fields) -> dict:
        actions = self.draft["actions"]
        action = {
            "temp_id": uuid.uuid4().hex,
            "action_name": fields.get("action_name", ""),
            "description": fields.get("description", ""),
            "instructions": fields.get("instructions", ""),
            "safety_notes": fields.get("safety_notes", ""),
            "notes": fields.get("notes", ""),
            "estimated_duration_minutes": fields.get("estimated_duration_minutes"),
            "sequence_order": fields.get("sequence_order") or (len(actions) + 1),
            "proto_action_item_id": fields.get("proto_action_item_id"),
            "tools": [],
            "part_demands": [],
        }
        actions.append(action)
        self._save()
        return action

    def add_action_from_proto(self, *, proto_action_item_id: int) -> dict:
        from app.maintenance.models.proto_templates.proto_action_item import ProtoActionItem

        proto = ProtoActionItem.objects.get(pk=proto_action_item_id, deleted_at__isnull=True)
        action = self.add_action(
            action_name=proto.action_name,
            description=proto.description,
            instructions=proto.instructions,
            safety_notes=proto.safety_notes,
            notes=proto.notes,
            estimated_duration_minutes=proto.estimated_duration_minutes,
            proto_action_item_id=proto.pk,
        )
        for tool in proto.proto_action_tools.filter(deleted_at__isnull=True).select_related("tool"):
            action["tools"].append(
                {
                    "tool_id": tool.tool_id,
                    "tool_name": tool.tool_name or (tool.tool.name if tool.tool_id else ""),
                    "quantity_required": tool.quantity_required,
                    "specifications": tool.specifications,
                    "notes": tool.notes,
                    "is_required": tool.is_required,
                }
            )
        for demand in proto.proto_part_demands.filter(deleted_at__isnull=True).select_related("part"):
            action["part_demands"].append(
                {
                    "part_id": demand.part_id,
                    "part_label": str(demand.part) if demand.part_id else "",
                    "quantity_required": float(demand.quantity_required),
                    "notes": demand.notes,
                    "is_optional": demand.is_optional,
                }
            )
        self._save()
        return action

    def add_action_from_template_item(self, *, template_action_item_id: int) -> dict:
        """Copy a step from another (already-published) maintenance template
        into this draft. A copy, not a link — the source template item keeps
        living on its own template set, and this draft's copy can diverge
        freely (same relationship add_action_from_proto has to the library)."""
        from app.maintenance.models.templates.template_action_item import TemplateActionItem

        source = TemplateActionItem.objects.get(
            pk=template_action_item_id, deleted_at__isnull=True
        )
        action = self.add_action(
            action_name=source.action_name,
            description=source.description,
            instructions=source.instructions,
            safety_notes=source.safety_notes,
            notes=source.notes,
            estimated_duration_minutes=source.estimated_duration_minutes,
            proto_action_item_id=source.proto_action_item_id,
        )
        for tool in source.template_action_tools.filter(deleted_at__isnull=True).select_related("tool"):
            action["tools"].append(
                {
                    "tool_id": tool.tool_id,
                    "tool_name": tool.tool_name or (tool.tool.name if tool.tool_id else ""),
                    "quantity_required": tool.quantity_required,
                    "specifications": tool.specifications,
                    "notes": tool.notes,
                    "is_required": tool.is_required,
                }
            )
        for demand in source.template_part_demands.filter(deleted_at__isnull=True).select_related("part"):
            action["part_demands"].append(
                {
                    "part_id": demand.part_id,
                    "part_label": str(demand.part) if demand.part_id else "",
                    "quantity_required": float(demand.quantity_required),
                    "notes": demand.notes,
                    "is_optional": demand.is_optional,
                }
            )
        self._save()
        return action

    def add_actions_from_template_set(self, *, template_action_set_id: int) -> list[dict]:
        """Copy every step of a published template into this draft, in order.

        The whole-template add the Action Creator Portal offers. Copies, like
        add_action_from_template_item — the draft owns its steps outright and
        keeps no link back to the set they came from.
        """
        source = TemplateActionSet.objects.get(
            pk=template_action_set_id, deleted_at__isnull=True
        )
        items = source.template_action_items.filter(deleted_at__isnull=True).order_by(
            "sequence_order"
        )
        return [
            self.add_action_from_template_item(template_action_item_id=item.pk)
            for item in items
        ]

    def duplicate_action(self, *, temp_id: str) -> dict:
        """Clone a step already in this draft, appended at the end.

        Deep-copies tools and part demands: the two steps are independent from
        the moment the copy exists, so editing one must never move the other.
        """
        source = self._find_action(temp_id)
        clone = copy.deepcopy(source)
        clone["temp_id"] = uuid.uuid4().hex
        clone["sequence_order"] = len(self.draft["actions"]) + 1
        self.draft["actions"].append(clone)
        self._save()
        return clone

    def move_action(self, *, temp_id: str, direction: str) -> None:
        """Swap a step with its neighbour. A no-op at either end rather than an
        error — the buttons are rendered disabled there, and a stale page
        should not raise."""
        actions = self.draft["actions"]
        index = next(
            (i for i, a in enumerate(actions) if a["temp_id"] == temp_id), None
        )
        if index is None:
            raise ValueError(f"Draft action '{temp_id}' not found.")
        target = index - 1 if direction == "up" else index + 1
        if not 0 <= target < len(actions):
            return
        actions[index], actions[target] = actions[target], actions[index]
        self._renumber_actions()
        self._save()

    def update_action(self, *, temp_id: str, **fields) -> dict:
        action = self._find_action(temp_id)
        for key, value in fields.items():
            if key in action:
                action[key] = value
        self._save()
        return action

    def remove_action(self, *, temp_id: str) -> None:
        self.draft["actions"] = [a for a in self.draft["actions"] if a["temp_id"] != temp_id]
        self._renumber_actions()
        self._save()

    def _renumber_actions(self) -> None:
        for index, action in enumerate(self.draft["actions"], start=1):
            action["sequence_order"] = index

    def _find_action(self, temp_id: str) -> dict:
        for action in self.draft["actions"]:
            if action["temp_id"] == temp_id:
                return action
        raise ValueError(f"Draft action '{temp_id}' not found.")

    # ------------------------------------------------------------------ #
    # Tools / part demands on a draft action
    # ------------------------------------------------------------------ #

    def add_tool(self, *, temp_id: str, **fields) -> dict:
        action = self._find_action(temp_id)
        tool = {
            "tool_id": fields.get("tool_id"),
            # Resolved once, at add time, so the draft is self-describing:
            # rendering a step must never need a join back to the catalog.
            "tool_name": fields.get("tool_name", "") or _tool_name(fields.get("tool_id")),
            "quantity_required": fields.get("quantity_required", 1),
            "specifications": fields.get("specifications", ""),
            "notes": fields.get("notes", ""),
            "is_required": fields.get("is_required", True),
        }
        action["tools"].append(tool)
        self._save()
        return tool

    def remove_tool(self, *, temp_id: str, tool_index: int) -> None:
        action = self._find_action(temp_id)
        if 0 <= tool_index < len(action["tools"]):
            action["tools"].pop(tool_index)
            self._save()

    def add_part_demand(self, *, temp_id: str, **fields) -> dict:
        action = self._find_action(temp_id)
        demand = {
            "part_id": fields["part_id"],
            "part_label": fields.get("part_label", "") or _part_label(fields["part_id"]),
            "quantity_required": fields.get("quantity_required", 1),
            "notes": fields.get("notes", ""),
            "is_optional": fields.get("is_optional", False),
        }
        action["part_demands"].append(demand)
        self._save()
        return demand

    def remove_part_demand(self, *, temp_id: str, demand_index: int) -> None:
        action = self._find_action(temp_id)
        if 0 <= demand_index < len(action["part_demands"]):
            action["part_demands"].pop(demand_index)
            self._save()

    # ------------------------------------------------------------------ #
    # Commit — the only path that touches the database
    # ------------------------------------------------------------------ #

    def commit(self, *, domain_id: int, actor=None) -> TemplateActionSet:
        draft = self.draft
        if not draft.get("task_name"):
            raise ValueError("task_name is required.")
        if draft.get("prior_revision_id") and not draft.get("revision_note", "").strip():
            raise ValueError("A revision note is required when publishing a revision.")

        with transaction.atomic():
            template_set = TemplateActionSet.objects.create(
                task_name=draft["task_name"],
                description=draft.get("description", ""),
                revision=draft.get("revision", "0"),
                prior_revision_id=draft.get("prior_revision_id"),
                asset_class_id=draft.get("asset_class_id"),
                domain_id=domain_id,
                is_active=True,
                created_by=actor,
                updated_by=actor,
            )
            template_set.asset_models.set(draft.get("asset_model_ids", []))
            for action in sorted(draft["actions"], key=lambda a: a["sequence_order"]):
                if not action.get("action_name"):
                    raise ValueError(
                        f"Action at sequence_order {action['sequence_order']} is "
                        "missing action_name."
                    )
                template_item = TemplateActionItem.objects.create(
                    template_action_set=template_set,
                    action_name=action["action_name"],
                    description=action.get("description", ""),
                    instructions=action.get("instructions", ""),
                    safety_notes=action.get("safety_notes", ""),
                    notes=action.get("notes", ""),
                    estimated_duration_minutes=action.get("estimated_duration_minutes"),
                    sequence_order=action["sequence_order"],
                    proto_action_item_id=action.get("proto_action_item_id"),
                    created_by=actor,
                    updated_by=actor,
                )
                for seq, tool in enumerate(action.get("tools", []), start=1):
                    TemplateActionTool.objects.create(
                        template_action_item=template_item,
                        tool_id=tool.get("tool_id"),
                        tool_name=tool.get("tool_name", ""),
                        quantity_required=tool.get("quantity_required", 1),
                        specifications=tool.get("specifications", ""),
                        notes=tool.get("notes", ""),
                        is_required=tool.get("is_required", True),
                        sequence_order=seq,
                        created_by=actor,
                        updated_by=actor,
                    )
                for seq, demand in enumerate(action.get("part_demands", []), start=1):
                    TemplatePartDemand.objects.create(
                        template_action_item=template_item,
                        part_id=demand["part_id"],
                        quantity_required=demand.get("quantity_required", 1),
                        notes=demand.get("notes", ""),
                        is_optional=demand.get("is_optional", False),
                        sequence_order=seq,
                        created_by=actor,
                        updated_by=actor,
                    )

            # Superseding a prior revision is opt-in at the draft level (set via
            # start_revision()) — never inferred, so a fresh non-revision build
            # never accidentally retires an unrelated template. The revision
            # note is recorded on the retiring (prior) template, not the new
            # one — it explains why *that* record is no longer current, which
            # is exactly the record template_detail shows it on.
            if draft.get("prior_revision_id"):
                TemplateActionSet.objects.filter(pk=draft["prior_revision_id"]).update(
                    is_active=False,
                    updated_by=actor,
                    revision_note=draft.get("revision_note", "").strip() or None,
                )

        self.clear()
        return template_set
