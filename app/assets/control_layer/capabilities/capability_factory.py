"""CapabilityFactory — copy-on-create cascade for the capability hierarchy.

Two static entry points, called from the creation seams in Phase 1:

  copy_class_to_model(model, actor)
      → called by AssetModelFactory.create() after the model row is committed.
      → copies active AssetClassCapability rows → ModelCapability (idempotent).
      → no events emitted (template copy only).

  copy_model_to_asset(asset, actor)
      → called by AssetCreationOrchestrator.create() inside its atomic block.
      → copies active ModelCapability rows → AssetCapability (idempotent).
      → emits one "Capability Added" Event + AssetEvent link per new row.

Both methods are idempotent: rows already present (by unique constraint) are
silently skipped.  Both run inside the caller's transaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.assets.models.capabilities import AssetCapability, AssetClassCapability, ModelCapability
from app.assets.models.core.asset_event import AssetEvent
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset, AssetModel


class CapabilityFactory:
    """Stateless copy-on-create logic for the capability cascade."""

    @staticmethod
    def copy_class_to_model(*, model: "AssetModel", actor: "AbstractUser") -> int:
        """Copy active AssetClassCapability rows to ModelCapability for this model.

        Returns the number of rows created.
        """
        class_caps = list(
            AssetClassCapability.objects.filter(
                asset_class_id=model.asset_class_id,
                is_active=True,
            ).select_related("capability_definition")
        )
        created_count = 0
        for cc in class_caps:
            _, created = ModelCapability.objects.get_or_create(
                model=model,
                capability_definition=cc.capability_definition,
                defaults={
                    "is_active": True,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            if created:
                created_count += 1
        return created_count

    @staticmethod
    def copy_model_to_asset(*, asset: "Asset", actor: "AbstractUser") -> int:
        """Copy active ModelCapability rows to AssetCapability for this asset.

        Creates one "Capability Added" Event + AssetEvent per new row.
        Returns the number of rows created.
        """
        model_caps = list(
            ModelCapability.objects.filter(
                model_id=asset.model_id,
                is_active=True,
            ).select_related("capability_definition")
        )
        created_count = 0
        for mc in model_caps:
            asset_cap, created = AssetCapability.objects.get_or_create(
                asset=asset,
                capability_definition=mc.capability_definition,
                defaults={
                    "is_active": True,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )
            if created:
                CapabilityFactory._emit_capability_added_event(
                    asset=asset,
                    capability_name=mc.capability_definition.name,
                    actor=actor,
                )
                created_count += 1
        return created_count

    @staticmethod
    def _emit_capability_added_event(
        *,
        asset: "Asset",
        capability_name: str,
        actor: "AbstractUser",
    ) -> None:
        title, description = AssetEventNarrator.capability_added_from_model(
            asset, capability_name
        )
        event = Event.objects.create(
            domain_id=asset.domain_id,
            title=title,
            description=description,
            event_type=EventType.ASSET_MANAGEMENT,
            status=EventStatus.COMPLETE,
            created_by=actor,
            updated_by=actor,
        )
        AssetEvent.objects.create(
            asset=asset,
            event=event,
            role="capability",
            created_by=actor,
            updated_by=actor,
        )
