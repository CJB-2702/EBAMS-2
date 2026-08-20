"""Manager: add, remove, and re-flag (required/preferred) the four
requirement types on a dispatch's manifest — capability, skill, model,
modification. A model row optionally carries a configuration template as
its own attribute, not a fifth requirement kind (a configuration means
nothing without a model as its subject). Material is handled separately by
DispatchDemandManager, since it raises a real demand rather than adding a
catalogue reference (doc 2 §7).

Locked out entirely once intent is frozen (IntentLockPolicy) — the manifest
is part of intent (doc 2 §10)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.dispatching.control_layer.guards.intent_lock_guard import IntentLockPolicy
from app.dispatching.control_layer.narrators.dispatch_narrator import DispatchNarrator
from app.dispatching.models.requirements.requested_capability import (
    DispatchRequestedCapability,
)
from app.dispatching.models.requirements.requested_model import DispatchRequestedModel
from app.dispatching.models.requirements.requested_modification import (
    DispatchRequestedModification,
)
from app.dispatching.models.requirements.requested_skill import DispatchRequestedSkill

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

#: kind -> (model, target FK field name, human label)
_REQUIREMENT_REGISTRY = {
    "capability": (DispatchRequestedCapability, "capability_definition_id", "capability"),
    "skill": (DispatchRequestedSkill, "skill_id", "skill"),
    "model": (DispatchRequestedModel, "model_id", "model"),
    "modification": (DispatchRequestedModification, "defined_modification_id", "modification"),
}


class RequirementManifestEditor:
    def __init__(self, dispatch_context) -> None:
        self._ctx = dispatch_context

    @property
    def dispatch(self):
        return self._ctx.dispatch

    def add(
        self,
        *,
        kind: str,
        target_id: int,
        is_required: bool = True,
        notes: str = "",
        quantity: int | None = None,
        minimum_level: int | None = None,
        configuration_template_id: int | None = None,
        actor: "AbstractUser",
    ):
        if kind not in _REQUIREMENT_REGISTRY:
            raise ValueError(f"Unknown requirement kind '{kind}'.")
        IntentLockPolicy.check_editable(dispatch=self.dispatch)

        model, target_field, label = _REQUIREMENT_REGISTRY[kind]
        create_kwargs = {
            "dispatch": self.dispatch,
            target_field: target_id,  # e.g. "capability_definition_id": 3
            "is_required": is_required,
            "notes": notes,
            "created_by": actor,
            "updated_by": actor,
        }
        if kind in ("skill", "model") and quantity is not None:
            create_kwargs["quantity"] = quantity
        if kind == "skill" and minimum_level is not None:
            create_kwargs["minimum_level"] = minimum_level
        if kind == "model" and configuration_template_id is not None:
            create_kwargs["configuration_template_id"] = configuration_template_id

        with transaction.atomic():
            row = model.objects.create(**create_kwargs)

        self._ctx._narrate(
            DispatchNarrator.requirement_added(
                requirement_kind=label, label=str(target_id), is_required=is_required
            )
        )
        self._ctx.refresh()
        return row

    def remove(self, *, kind: str, requirement_id: int, actor: "AbstractUser") -> None:
        if kind not in _REQUIREMENT_REGISTRY:
            raise ValueError(f"Unknown requirement kind '{kind}'.")
        IntentLockPolicy.check_editable(dispatch=self.dispatch)

        model, _, label = _REQUIREMENT_REGISTRY[kind]
        row = model.objects.get(pk=requirement_id, dispatch_id=self.dispatch.pk)
        with transaction.atomic():
            row.delete()

        self._ctx._narrate(
            DispatchNarrator.requirement_removed(requirement_kind=label, label=str(requirement_id))
        )
        self._ctx.refresh()

    def set_required_flag(self, *, kind: str, requirement_id: int, is_required: bool, actor: "AbstractUser"):
        if kind not in _REQUIREMENT_REGISTRY:
            raise ValueError(f"Unknown requirement kind '{kind}'.")
        IntentLockPolicy.check_editable(dispatch=self.dispatch)

        model, _, _ = _REQUIREMENT_REGISTRY[kind]
        row = model.objects.get(pk=requirement_id, dispatch_id=self.dispatch.pk)
        row.is_required = is_required
        row.updated_by = actor
        row.save(update_fields=["is_required", "updated_by", "updated_at"])
        self._ctx.refresh()
        return row
