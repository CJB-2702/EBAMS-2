"""ModificationManager — DefinedModification catalog and ActualModification lifecycle.

Owns two concerns:
  1. The catalog of DefinedModification entries (create/update/deactivate/delete).
  2. Recording and retiring ActualModification rows on individual assets, with
     creation_event and removal_event links wired to the events app.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.models.configurations import ActualModification, DefinedModification
from app.assets.models.core.asset_event import AssetEvent
from app.assets.control_layer.guards.modification_applicability_guard import (
    ModificationApplicabilityValidator,
)
from app.assets.control_layer.narrators.asset_event_narrator import AssetEventNarrator
from app.events.models import Event, EventStatus, EventType

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from app.assets.models import Asset


class ModificationManager:
    """Manages the DefinedModification catalog and ActualModification records."""

    def __init__(self, actor: "AbstractUser") -> None:
        self.actor = actor

    # ── DefinedModification catalog ──────────────────────────────────────────

    def create_defined_modification(
        self,
        *,
        name: str,
        code: str,
        category: str | None = None,
        description: str | None = None,
    ) -> DefinedModification:
        name = name.strip()
        code = code.strip().upper()
        if not name:
            raise ValueError("Modification name is required.")
        if not code:
            raise ValueError("Modification code is required.")
        if DefinedModification.objects.filter(code=code).exists():
            raise ValueError(f"A DefinedModification with code '{code}' already exists.")
        return DefinedModification.objects.create(
            name=name,
            code=code,
            category=(category or "").strip() or None,
            description=(description or "").strip() or None,
            is_active=True,
            created_by=self.actor,
            updated_by=self.actor,
        )

    def update_defined_modification(
        self,
        defined_mod: DefinedModification,
        *,
        name: str | None = None,
        code: str | None = None,
        category: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> DefinedModification:
        if name is not None:
            name = name.strip()
            if not name:
                raise ValueError("Modification name cannot be blank.")
            defined_mod.name = name
        if code is not None:
            code = code.strip().upper()
            if not code:
                raise ValueError("Modification code cannot be blank.")
            if (
                DefinedModification.objects.filter(code=code)
                .exclude(pk=defined_mod.pk)
                .exists()
            ):
                raise ValueError(f"A DefinedModification with code '{code}' already exists.")
            defined_mod.code = code
        if category is not None:
            defined_mod.category = category.strip() or None
        if description is not None:
            defined_mod.description = description.strip() or None
        if is_active is not None:
            defined_mod.is_active = is_active
        defined_mod.updated_by = self.actor
        defined_mod.save()
        return defined_mod

    def deactivate_defined_modification(
        self, defined_mod: DefinedModification
    ) -> DefinedModification:
        defined_mod.is_active = False
        defined_mod.updated_by = self.actor
        defined_mod.save()
        return defined_mod

    def delete_defined_modification(self, defined_mod: DefinedModification) -> None:
        """Hard-delete only if no template or actual references exist."""
        has_template_links = defined_mod.template_links.exists()
        has_actual_links = defined_mod.actual_applications.exists()
        if has_template_links or has_actual_links:
            raise ValueError(
                f"Cannot delete DefinedModification '{defined_mod.name}': "
                f"referenced by existing template or actual modification records."
            )
        defined_mod.delete()

    # ── ActualModification on assets ─────────────────────────────────────────

    def add_actual_modification(
        self,
        *,
        asset: "Asset",
        defined_modification: DefinedModification,
        applied_at: datetime.date | None = None,
        notes: str | None = None,
    ) -> ActualModification:
        # Checkpoint 3 — runtime applicability gate. Raises before any side effect
        # if this modification's applicability forbids this asset.
        ModificationApplicabilityValidator.check(asset, defined_modification)
        with transaction.atomic():
            title, description = AssetEventNarrator.modification_added(
                asset, defined_modification.name
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
                role="modification",
                created_by=self.actor,
                updated_by=self.actor,
            )
            actual_mod = ActualModification.objects.create(
                asset=asset,
                defined_modification=defined_modification,
                applied_at=applied_at,
                notes=(notes or "").strip() or None,
                is_active=True,
                creation_event=event,
                created_by=self.actor,
                updated_by=self.actor,
            )
        return actual_mod

    def update_actual_modification(
        self,
        actual_mod: ActualModification,
        *,
        applied_at: datetime.date | None = None,
        notes: str | None = None,
    ) -> ActualModification:
        if applied_at is not None:
            actual_mod.applied_at = applied_at
        if notes is not None:
            actual_mod.notes = (notes or "").strip() or None
        actual_mod.updated_by = self.actor
        actual_mod.save()
        return actual_mod

    def remove_actual_modification(
        self, actual_mod: ActualModification
    ) -> ActualModification:
        if not actual_mod.is_active:
            return actual_mod
        with transaction.atomic():
            title, description = AssetEventNarrator.modification_removed(
                actual_mod.asset, actual_mod.defined_modification.name
            )
            event = Event.objects.create(
                domain_id=actual_mod.asset.domain_id,
                title=title,
                description=description,
                event_type=EventType.ASSET_MANAGEMENT,
                status=EventStatus.COMPLETE,
                created_by=self.actor,
                updated_by=self.actor,
            )
            AssetEvent.objects.create(
                asset=actual_mod.asset,
                event=event,
                role="modification",
                created_by=self.actor,
                updated_by=self.actor,
            )
            actual_mod.removal_event = event
            actual_mod.is_active = False
            actual_mod.updated_by = self.actor
            actual_mod.save()
        return actual_mod
