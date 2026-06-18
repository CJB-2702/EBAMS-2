"""CapabilityDefinitionContext — control logic around one capability-definition id.

Owns the catalog metadata update verb plus the class/model assignment-set sync
verbs. Class and model links are reconciled as sets (add missing, drop removed) so
the editor submits the *desired* full state and the context computes the delta.

This mirrors ``AssetClassContext``: the live capability verticals treat
``AssetClassCapability`` / ``ModelCapability`` rows as hard create/delete, so the
reconcile here deletes dropped rows rather than soft-deactivating them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.guards.capability_definition_uniqueness_guard import (
    CapabilityDefinitionUniquenessValidator,
)
from app.assets.models.capabilities import (
    AssetClassCapability,
    CapabilityDefinition,
    ModelCapability,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

_METADATA_FIELDS = ("name", "code", "description", "is_active")


class CapabilityDefinitionValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class CapabilityDefinitionContext:
    def __init__(self, definition_id: int, actor: "AbstractUser") -> None:
        self.actor = actor
        self.definition = CapabilityDefinition.objects.get(id=definition_id)

    # ── Metadata ─────────────────────────────────────────────────────────────
    def update(self, *, data: dict) -> CapabilityDefinition:
        candidate_name = data.get("name", self.definition.name)
        candidate_code = data.get("code", self.definition.code)
        errors = CapabilityDefinitionUniquenessValidator.validate(
            name=candidate_name,
            code=candidate_code,
            exclude_definition_id=self.definition.id,
        )
        if errors:
            raise CapabilityDefinitionValidationError(errors)

        d = self.definition
        changed: list[str] = []
        with transaction.atomic():
            for field in _METADATA_FIELDS:
                if field in data:
                    value = data[field]
                    if field == "name":
                        value = (value or "").strip()
                    elif field == "code":
                        value = (value or "").strip().upper()
                    elif field == "description":
                        value = value or None
                    setattr(d, field, value)
                    changed.append(field)
            if changed:
                d.updated_by = self.actor
                d.save(update_fields=[*changed, "updated_at", "updated_by"])
        return d

    # ── Assignment-set sync ──────────────────────────────────────────────────
    def set_classes(self, *, class_ids: list[int]) -> None:
        """Reconcile which asset classes declare this capability."""
        desired = set(class_ids)
        with transaction.atomic():
            existing = dict(
                AssetClassCapability.objects.filter(
                    capability_definition=self.definition
                ).values_list("asset_class_id", "id")
            )
            to_add = desired - existing.keys()
            to_remove_ids = [
                row_id for class_id, row_id in existing.items() if class_id not in desired
            ]
            for class_id in to_add:
                AssetClassCapability.objects.create(
                    asset_class_id=class_id,
                    capability_definition=self.definition,
                    is_active=True,
                    created_by=self.actor,
                    updated_by=self.actor,
                )
            if to_remove_ids:
                AssetClassCapability.objects.filter(id__in=to_remove_ids).delete()

    def set_models(self, *, model_ids: list[int]) -> None:
        """Reconcile which asset models declare this capability."""
        desired = set(model_ids)
        with transaction.atomic():
            existing = dict(
                ModelCapability.objects.filter(
                    capability_definition=self.definition
                ).values_list("model_id", "id")
            )
            to_add = desired - existing.keys()
            to_remove_ids = [
                row_id for model_id, row_id in existing.items() if model_id not in desired
            ]
            for model_id in to_add:
                ModelCapability.objects.create(
                    model_id=model_id,
                    capability_definition=self.definition,
                    is_active=True,
                    created_by=self.actor,
                    updated_by=self.actor,
                )
            if to_remove_ids:
                ModelCapability.objects.filter(id__in=to_remove_ids).delete()
