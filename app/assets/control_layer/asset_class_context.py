"""AssetClassContext — entry point for control logic around one asset-class id.

Owns the metadata/domain update verb and the capability-set sync verb. Domain and
capability links are reconciled as sets (add missing, remove dropped) so the editor
submits the *desired* full state and the context computes the delta.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.domain_structs.asset_class_struct import AssetClassStruct
from app.assets.control_layer.guards.asset_class_uniqueness_guard import (
    AssetClassUniquenessValidator,
)
from app.assets.models import AssetClassCapability, AssetClassDomain

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import AssetClass

_METADATA_FIELDS = ("name", "category", "description", "restrict_to_domain_set")


class AssetClassValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class AssetClassContext:
    def __init__(
        self, class_id: int, actor: "AbstractUser", *, eager: bool = False
    ) -> None:
        self.actor = actor
        self.struct = AssetClassStruct(class_id, eager=eager)
        self.asset_class: "AssetClass" = self.struct.asset_class

    @classmethod
    def from_struct(
        cls, struct: AssetClassStruct, actor: "AbstractUser"
    ) -> "AssetClassContext":
        ctx = cls.__new__(cls)
        ctx.actor = actor
        ctx.struct = struct
        ctx.asset_class = struct.asset_class
        return ctx

    # ── Domain verbs ─────────────────────────────────────────────────────────
    def update(self, *, data: dict) -> "AssetClass":
        """Apply metadata fields and reconcile the linked domain set."""
        candidate_name = data.get("name", self.asset_class.name)
        errors = AssetClassUniquenessValidator.validate(
            name=candidate_name,
            exclude_class_id=self.asset_class.id,
        )
        if errors:
            raise AssetClassValidationError(errors)

        c = self.asset_class
        with transaction.atomic():
            changed: list[str] = []
            for field in _METADATA_FIELDS:
                if field in data:
                    value = data[field]
                    if field == "name":
                        value = (value or "").strip()
                    elif field in ("category", "description"):
                        value = value or None
                    setattr(c, field, value)
                    changed.append(field)
            if changed:
                c.updated_by = self.actor
                c.save(update_fields=[*changed, "updated_at", "updated_by"])

            if "domain_ids" in data:
                self._sync_domains(desired_ids=set(data["domain_ids"]))

        return c

    def set_capabilities(self, *, capability_ids: list[int]) -> None:
        """Reconcile declared class capabilities to the desired definition set."""
        desired = set(capability_ids)
        with transaction.atomic():
            existing = dict(
                AssetClassCapability.objects.filter(
                    asset_class=self.asset_class
                ).values_list("capability_definition_id", "id")
            )
            to_add = desired - existing.keys()
            to_remove_ids = [
                row_id
                for def_id, row_id in existing.items()
                if def_id not in desired
            ]
            for def_id in to_add:
                AssetClassCapability.objects.create(
                    asset_class=self.asset_class,
                    capability_definition_id=def_id,
                    is_active=True,
                    created_by=self.actor,
                    updated_by=self.actor,
                )
            if to_remove_ids:
                AssetClassCapability.objects.filter(id__in=to_remove_ids).delete()

    # ── Internals ────────────────────────────────────────────────────────────
    def _sync_domains(self, *, desired_ids: set[int]) -> None:
        existing = dict(
            AssetClassDomain.objects.filter(
                asset_class=self.asset_class
            ).values_list("domain_id", "id")
        )
        to_add = desired_ids - existing.keys()
        to_remove_ids = [
            row_id for domain_id, row_id in existing.items() if domain_id not in desired_ids
        ]
        for domain_id in to_add:
            AssetClassDomain.objects.create(
                asset_class=self.asset_class,
                domain_id=domain_id,
                created_by=self.actor,
                updated_by=self.actor,
            )
        if to_remove_ids:
            AssetClassDomain.objects.filter(id__in=to_remove_ids).delete()
