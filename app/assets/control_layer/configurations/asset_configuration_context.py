"""AssetConfigurationContext — orchestrates one asset's configuration save.

The edit screen submits a single form covering three concerns: the baseline
template, the verification status / notes, and the desired set of actual
modifications. This context coordinates the existing managers
(``ConfigurationManager`` for the template assignment + status, and
``ModificationManager`` for the modification set-reconcile) inside one workflow so
the entrypoint stays thin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from app.assets.control_layer.configurations.configuration_manager import (
    ConfigurationManager,
)
from app.assets.control_layer.configurations.modification_manager import (
    ModificationManager,
)
from app.assets.models import Asset, ConfigurationTemplate

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class AssetConfigurationContext:
    def __init__(self, asset_id: int, actor: "AbstractUser") -> None:
        self.actor = actor
        self.asset = Asset.objects.select_related("model", "asset_class", "domain").get(
            id=asset_id
        )
        self.configurations = ConfigurationManager(actor)
        self.modifications = ModificationManager(actor)

    def save(
        self,
        *,
        template_id: int | None,
        verification_status: str | None,
        notes: str | None,
        modification_ids: list[int],
    ) -> None:
        """Assign/keep the template, update status + notes, reconcile mods."""
        with transaction.atomic():
            config = self.configurations.get_current(self.asset)

            if template_id is not None:
                if config is None or config.template_id != template_id:
                    template = ConfigurationTemplate.objects.get(id=template_id)
                    config = self.configurations.assign(
                        asset=self.asset, template=template, notes=notes
                    )

            if config is not None:
                if verification_status is not None:
                    self.configurations.update_verification_status(
                        config, verification_status
                    )
                self.configurations.update_notes(config, notes or "")

            self.modifications.set_asset_modifications(
                asset=self.asset, modification_ids=modification_ids
            )
