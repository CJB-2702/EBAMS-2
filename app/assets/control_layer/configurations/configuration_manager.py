"""ConfigurationManager — AssetConfiguration lifecycle.

Assigns configuration templates to assets and manages the documentation
status of each assignment.  Multiple configurations per asset are allowed;
the current one is always the most recently created (latest wins).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from app.assets.models.configurations import AssetConfiguration, VerificationStatus
from app.assets.models.core.asset_event import AssetEvent
from app.assets.control_layer.guards.configuration_assignment_guard import (
    ConfigurationAssignmentValidator,
)
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset, ConfigurationTemplate


class ConfigurationManager:
    """Manages the AssetConfiguration lifecycle for a single asset."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    # ── Assignment ───────────────────────────────────────────────────────────

    def assign(
        self,
        *,
        asset: "Asset",
        template: "ConfigurationTemplate",
        notes: str | None = None,
    ) -> AssetConfiguration:
        """Create a new AssetConfiguration linking asset → template.

        Multiple configurations per asset are permitted; the most recently
        created row is authoritative (latest wins).  No previous rows are
        mutated.
        """
        ConfigurationAssignmentValidator.check(asset, template)
        with transaction.atomic():
            config = AssetConfiguration.objects.create(
                asset=asset,
                template=template,
                notes=(notes or "").strip() or None,
                verification_status=VerificationStatus.UNVERIFIED,
                is_current=True,
                created_by=self.actor,
                updated_by=self.actor,
            )
            self._emit_assigned_event(asset=asset, template=template)
        return config

    # ── Status / notes mutations ─────────────────────────────────────────────

    def update_verification_status(
        self,
        config: AssetConfiguration,
        new_status: str,
    ) -> AssetConfiguration:
        if new_status not in VerificationStatus.values:
            raise ValueError(
                f"Invalid verification_status '{new_status}'. "
                f"Must be one of {VerificationStatus.values}."
            )
        config.verification_status = new_status
        config.updated_by = self.actor
        if new_status == VerificationStatus.COMPLETE and config.documented_at is None:
            config.documented_at = timezone.now()
        config.save()
        return config

    def update_notes(self, config: AssetConfiguration, notes: str) -> AssetConfiguration:
        config.notes = (notes or "").strip() or None
        config.updated_by = self.actor
        config.save()
        return config

    # ── Queries ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_current(asset: "Asset") -> AssetConfiguration | None:
        """Return the most recently created AssetConfiguration for this asset."""
        return (
            AssetConfiguration.objects.filter(asset=asset)
            .order_by("-created_at")
            .first()
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _emit_assigned_event(
        self,
        *,
        asset: "Asset",
        template: "ConfigurationTemplate",
    ) -> None:
        title, description = AssetEventNarrator.configuration_assigned(
            asset, template.name
        )
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
            role="configuration",
            created_by=self.actor,
            updated_by=self.actor,
        )
