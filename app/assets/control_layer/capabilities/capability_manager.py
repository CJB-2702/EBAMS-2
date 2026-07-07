"""CapabilityManager — asset-layer capability set-reconcile, event-tracked.

Catalog CRUD lives on ``CapabilityDefinitionFactory`` (create) and
``CapabilityDefinitionContext`` (edit metadata + class/model assignment sets).
This manager owns only the asset layer: reconciling an asset's manual
(non-inherited) ``AssetCapability`` rows, and the inverse bulk editor that
reconciles which assets carry one definition. Adds and removes emit
Events + AssetEvent links (auditable); class/model assignment is
administrative and does not.
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
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset


class CapabilityManager:
    """Reconciles asset-layer capability rows. Event-tracked."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

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
