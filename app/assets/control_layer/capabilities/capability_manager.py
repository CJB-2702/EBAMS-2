"""CapabilityManager — day-to-day CRUD across all four capability layers.

Routes:
  Catalog:     define / deactivate_definition
  Class layer: add_to_class / remove_from_class / update_class_capability
  Model layer: add_to_model / remove_from_model / update_model_capability
  Asset layer: add_to_asset / remove_from_asset / annotate_asset_capability

Asset-layer mutations emit Events + AssetEvent links (auditable).
Class/model mutations are administrative and do not emit events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models.capabilities import (
    AssetCapability,
    AssetClassCapability,
    CapabilityDefinition,
    ModelCapability,
)
from app.assets.models.core.asset_event import AssetEvent
from app.assets.control_layer.guards.capability_assignment_guard import (
    CapabilityAssignmentValidator,
)
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset, AssetClass, AssetModel


class CapabilityManager:
    """Manages capabilities across all four layers."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    # ── Catalog (CapabilityDefinition) ───────────────────────────────────────

    def define(
        self,
        *,
        name: str,
        code: str,
        description: str | None = None,
    ) -> CapabilityDefinition:
        name = name.strip()
        code = code.strip().upper()
        if not name:
            raise ValueError("Capability name is required.")
        if not code:
            raise ValueError("Capability code is required.")
        if CapabilityDefinition.objects.filter(name=name).exists():
            raise ValueError(f"A CapabilityDefinition named '{name}' already exists.")
        if CapabilityDefinition.objects.filter(code=code).exists():
            raise ValueError(f"A CapabilityDefinition with code '{code}' already exists.")
        return CapabilityDefinition.objects.create(
            name=name,
            code=code,
            description=(description or "").strip() or None,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def deactivate_definition(
        self, cap_def: CapabilityDefinition
    ) -> CapabilityDefinition:
        cap_def.is_active = False
        cap_def.updated_by = self.actor
        cap_def.save()
        return cap_def

    # ── Class layer (AssetClassCapability) ───────────────────────────────────

    def add_to_class(
        self,
        *,
        asset_class: "AssetClass",
        cap_def: CapabilityDefinition,
    ) -> AssetClassCapability:
        CapabilityAssignmentValidator.check_definition_active(cap_def)
        CapabilityAssignmentValidator.check_no_duplicate_class(asset_class, cap_def)
        return AssetClassCapability.objects.create(
            asset_class=asset_class,
            capability_definition=cap_def,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def remove_from_class(self, class_cap: AssetClassCapability) -> AssetClassCapability:
        class_cap.is_active = False
        class_cap.updated_by = self.actor
        class_cap.save()
        return class_cap

    def update_class_capability(
        self,
        class_cap: AssetClassCapability,
        *,
        is_active: bool | None = None,
    ) -> AssetClassCapability:
        if is_active is not None:
            class_cap.is_active = is_active
        class_cap.updated_by = self.actor
        class_cap.save()
        return class_cap

    # ── Model layer (ModelCapability) ─────────────────────────────────────────

    def add_to_model(
        self,
        *,
        model: "AssetModel",
        cap_def: CapabilityDefinition,
    ) -> ModelCapability:
        CapabilityAssignmentValidator.check_definition_active(cap_def)
        CapabilityAssignmentValidator.check_no_duplicate_model(model, cap_def)
        return ModelCapability.objects.create(
            model=model,
            capability_definition=cap_def,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def remove_from_model(self, model_cap: ModelCapability) -> ModelCapability:
        model_cap.is_active = False
        model_cap.updated_by = self.actor
        model_cap.save()
        return model_cap

    def update_model_capability(
        self,
        model_cap: ModelCapability,
        *,
        is_active: bool | None = None,
    ) -> ModelCapability:
        if is_active is not None:
            model_cap.is_active = is_active
        model_cap.updated_by = self.actor
        model_cap.save()
        return model_cap

    # ── Asset layer (AssetCapability) — event-tracked ─────────────────────────

    def add_to_asset(
        self,
        *,
        asset: "Asset",
        cap_def: CapabilityDefinition,
        qty: int | None = None,
        notes: str | None = None,
    ) -> AssetCapability:
        CapabilityAssignmentValidator.check_definition_active(cap_def)
        CapabilityAssignmentValidator.check_no_duplicate_asset(asset, cap_def)
        with transaction.atomic():
            asset_cap = AssetCapability.objects.create(
                asset=asset,
                capability_definition=cap_def,
                is_active=True,
                qty=qty,
                notes=(notes or "").strip() or None,
                created_by=self.actor,
                updated_by=self.actor,
            )
            self._emit_event(
                asset=asset,
                title_fn=lambda: AssetEventNarrator.capability_added(
                    asset, cap_def.name
                ),
                role="capability",
            )
        return asset_cap

    def remove_from_asset(self, asset_cap: AssetCapability) -> AssetCapability:
        if not asset_cap.is_active:
            return asset_cap
        with transaction.atomic():
            self._emit_event(
                asset=asset_cap.asset,
                title_fn=lambda: AssetEventNarrator.capability_removed(
                    asset_cap.asset,
                    asset_cap.capability_definition.name,
                ),
                role="capability",
            )
            asset_cap.is_active = False
            asset_cap.updated_by = self.actor
            asset_cap.save()
        return asset_cap

    def annotate_asset_capability(
        self,
        asset_cap: AssetCapability,
        *,
        qty: int | None = None,
        notes: str | None = None,
    ) -> AssetCapability:
        if qty is not None:
            asset_cap.qty = qty
        if notes is not None:
            asset_cap.notes = (notes or "").strip() or None
        asset_cap.updated_by = self.actor
        asset_cap.save()
        return asset_cap

    # ── Asset layer — set-reconcile editors ──────────────────────────────────

    def set_asset_capabilities(
        self,
        *,
        asset: "Asset",
        desired: list[dict],
    ) -> None:
        """Reconcile one asset's DIRECT (manual) capability rows to ``desired``.

        ``desired`` is the full submitted set: each item ``{definition_id, qty,
        notes, is_active}``. Inherited rows (present on the class or model
        template) are never touched here — the editor only manages manual adds.
        Hard create/delete (matching the class/model verticals); adds and removes
        emit asset events.
        """
        inherited_def_ids = self._inherited_definition_ids(asset)
        existing_manual = {
            ac.capability_definition_id: ac
            for ac in AssetCapability.objects.filter(asset=asset).select_related(
                "capability_definition"
            )
            if ac.capability_definition_id not in inherited_def_ids
        }
        desired_by_def = {int(item["definition_id"]): item for item in desired}

        to_add = desired_by_def.keys() - existing_manual.keys()
        to_remove = existing_manual.keys() - desired_by_def.keys()

        with transaction.atomic():
            for def_id in to_remove:
                self._delete_asset_capability(existing_manual[def_id])

            cap_defs = {
                cd.id: cd
                for cd in CapabilityDefinition.objects.filter(id__in=to_add)
            }
            for def_id in to_add:
                cap_def = cap_defs[def_id]
                item = desired_by_def[def_id]
                self._create_asset_capability(
                    asset=asset,
                    cap_def=cap_def,
                    qty=item.get("qty"),
                    notes=item.get("notes"),
                    is_active=item.get("is_active", True),
                )

            for def_id in desired_by_def.keys() & existing_manual.keys():
                self._apply_asset_capability_fields(
                    existing_manual[def_id], desired_by_def[def_id]
                )

    def set_definition_assets(
        self,
        *,
        cap_def: CapabilityDefinition,
        desired: list[dict],
    ) -> None:
        """Reconcile which assets carry ``cap_def`` as a direct row (bulk editor).

        ``desired`` is the full submitted set: each item ``{asset_id, qty, notes,
        is_active}``. Hard create/delete; adds and removes emit asset events.
        """
        from app.assets.models import Asset

        existing = {
            ac.asset_id: ac
            for ac in AssetCapability.objects.filter(capability_definition=cap_def)
        }
        desired_by_asset = {int(item["asset_id"]): item for item in desired}

        to_add = desired_by_asset.keys() - existing.keys()
        to_remove = existing.keys() - desired_by_asset.keys()

        with transaction.atomic():
            for asset_id in to_remove:
                self._delete_asset_capability(existing[asset_id])

            assets = {a.id: a for a in Asset.objects.filter(id__in=to_add)}
            for asset_id in to_add:
                asset = assets[asset_id]
                item = desired_by_asset[asset_id]
                self._create_asset_capability(
                    asset=asset,
                    cap_def=cap_def,
                    qty=item.get("qty"),
                    notes=item.get("notes"),
                    is_active=item.get("is_active", True),
                )

            for asset_id in desired_by_asset.keys() & existing.keys():
                self._apply_asset_capability_fields(
                    existing[asset_id], desired_by_asset[asset_id]
                )

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _inherited_definition_ids(asset: "Asset") -> set[int]:
        """Capability-definition ids this asset inherits from its class or model."""
        class_ids = set(
            AssetClassCapability.objects.filter(
                asset_class_id=asset.asset_class_id, is_active=True
            ).values_list("capability_definition_id", flat=True)
        )
        model_ids = set(
            ModelCapability.objects.filter(
                model_id=asset.model_id, is_active=True
            ).values_list("capability_definition_id", flat=True)
        )
        return class_ids | model_ids

    def _create_asset_capability(
        self,
        *,
        asset: "Asset",
        cap_def: CapabilityDefinition,
        qty: int | None,
        notes: str | None,
        is_active: bool,
    ) -> AssetCapability:
        asset_cap = AssetCapability.objects.create(
            asset=asset,
            capability_definition=cap_def,
            is_active=is_active,
            qty=qty,
            notes=(notes or "").strip() or None,
            created_by=self.actor,
            updated_by=self.actor,
        )
        self._emit_event(
            asset=asset,
            title_fn=lambda: AssetEventNarrator.capability_added(asset, cap_def.name),
            role="capability",
        )
        return asset_cap

    def _delete_asset_capability(self, asset_cap: AssetCapability) -> None:
        asset = asset_cap.asset
        cap_name = asset_cap.capability_definition.name
        self._emit_event(
            asset=asset,
            title_fn=lambda: AssetEventNarrator.capability_removed(asset, cap_name),
            role="capability",
        )
        asset_cap.delete()

    def _apply_asset_capability_fields(
        self, asset_cap: AssetCapability, item: dict
    ) -> None:
        asset_cap.qty = item.get("qty")
        asset_cap.notes = (item.get("notes") or "").strip() or None
        asset_cap.is_active = item.get("is_active", True)
        asset_cap.updated_by = self.actor
        asset_cap.save(
            update_fields=["qty", "notes", "is_active", "updated_at", "updated_by"]
        )

    def _emit_event(
        self,
        *,
        asset: "Asset",
        title_fn,
        role: str,
    ) -> None:
        title, description = title_fn()
        event = Event.objects.create(
            domain_id=asset.domain_id,
            title=title,
            description=description,
            event_type=EventType.ASSET_MANAGEMENT,
            status=EventStatus.COMPLETE,
            created_by=self.actor,
            updated_by=self.actor,
        )
        AssetEvent.objects.create(
            asset=asset,
            event=event,
            role=role,
            created_by=self.actor,
            updated_by=self.actor,
        )
