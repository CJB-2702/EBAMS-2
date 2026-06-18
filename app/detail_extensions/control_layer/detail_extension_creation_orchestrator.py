"""DetailExtensionCreationOrchestrator — the single create-time listener.

The detail_extensions counterpart to the assets-side ``AssetCreationOrchestrator``:
one named fan-in point that listens to **both** owner-creation signals and schedules
post-commit provisioning. It is the only place that connects to the assets signals.

Flow (per owner created):

    assets emits asset_created / asset_model_created  (last in-transaction statement)
        → this orchestrator's receiver runs (still inside the create transaction)
        → schedules transaction.on_commit(...)        (pk + actor_id, never the instance)
            → AFTER the owner commits: the matching provisioner runs in its own
              transaction and creates the extension rows.

Receivers are **thin** — they only schedule. All provisioning logic stays in the
per-target provisioner workers. A package installer (future) sits above this seam by
writing enablement rows; provisioning then follows with no change here.
"""

from __future__ import annotations

import logging
from functools import partial

from django.db import transaction

from app.assets.signals import asset_created, asset_model_created
from app.detail_extensions.control_layer.provisioning.asset_extension_provisioner import (
    AssetExtensionProvisioner,
)
from app.detail_extensions.control_layer.provisioning.model_extension_provisioner import (
    ModelExtensionProvisioner,
)

logger = logging.getLogger(__name__)

_ASSET_UID = "detail_extensions.on_asset_created"
_MODEL_UID = "detail_extensions.on_asset_model_created"


class DetailExtensionCreationOrchestrator:
    """Listens to owner-creation signals; schedules post-commit provisioning."""

    @classmethod
    def connect(cls) -> None:
        asset_created.connect(
            cls.on_asset_created, dispatch_uid=_ASSET_UID, weak=False
        )
        asset_model_created.connect(
            cls.on_asset_model_created, dispatch_uid=_MODEL_UID, weak=False
        )

    # ── Receivers (thin — schedule only) ─────────────────────────────────────
    @staticmethod
    def on_asset_created(sender, asset, actor_id=None, **kwargs) -> None:
        transaction.on_commit(
            partial(_provision_asset, asset_id=asset.pk, actor_id=actor_id)
        )

    @staticmethod
    def on_asset_model_created(sender, model, actor_id=None, **kwargs) -> None:
        transaction.on_commit(
            partial(_provision_model, model_id=model.pk, actor_id=actor_id)
        )


def _provision_asset(*, asset_id: int, actor_id: int | None) -> None:
    """Post-commit entry point. Swallows + logs so a provisioning failure never
    surfaces as a creation error (the asset already committed)."""
    try:
        AssetExtensionProvisioner.provision_for_asset(
            asset_id=asset_id, actor_id=actor_id
        )
    except Exception:
        logger.exception("Post-commit asset extension provisioning failed (asset=%s).", asset_id)


def _provision_model(*, model_id: int, actor_id: int | None) -> None:
    try:
        ModelExtensionProvisioner.provision_for_model(
            model_id=model_id, actor_id=actor_id
        )
    except Exception:
        logger.exception("Post-commit model extension provisioning failed (model=%s).", model_id)
