"""AssetCreationOrchestrator — the single, explicit create-time fan-out (kit D1).

Names every follow-on step of asset creation and runs them in one
``transaction.atomic()`` block. Adding a step later means editing this method —
an intentional, visible cost. Capability copy (P4) is filled; P3 remains an ordered
no-op. Extension provisioning is no longer called here: creation emits
``asset_created`` as its last in-transaction statement and ``detail_extensions``
provisions post-commit by listening (the dependency was inverted in P2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.capabilities.capability_factory import CapabilityFactory
from app.assets.control_layer.factories.asset_factory import AssetFactory
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.assets.signals import asset_created
from app.assets.models import Asset, AssetEvent
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetCreationOrchestrator:
    @classmethod
    def create(cls, *, data: dict, actor: "AbstractUser") -> "Asset":
        with transaction.atomic():
            # 1. Root + required threads.
            asset = AssetFactory.create(data=data, actor=actor)

            # 2. Lifecycle event + asset↔event link.
            cls._emit_created_event(asset=asset, actor=actor)

            # P3: (no default configuration assignment at creation — explicit only)

            # 3. P4: copy model capability templates to asset.
            CapabilityFactory.copy_model_to_asset(asset=asset, actor=actor)

            # 4. Announce — last in-transaction statement. detail_extensions listens
            #    and provisions post-commit; assets stays ignorant of extensions.
            asset_created.send(
                sender=Asset, asset=asset, actor_id=getattr(actor, "pk", None)
            )

        return asset

    @staticmethod
    def _emit_created_event(*, asset: "Asset", actor: "AbstractUser") -> None:
        title, description = AssetEventNarrator.asset_created(asset)
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
            role="lifecycle",
            created_by=actor,
            updated_by=actor,
        )
