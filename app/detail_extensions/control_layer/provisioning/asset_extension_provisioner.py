"""AssetExtensionProvisioner — provisions enabled extensions for one asset.

A worker the ``DetailExtensionCreationOrchestrator`` delegates to. Runs **post-commit
in its own transaction** (the asset already committed): it re-fetches the owner by id,
reads the class/model enablement, and creates the missing extension rows.

Idempotency / backfill (E7) is tracked in ``AssetExtensionProvisioningState`` — a
durable per-asset list of provisioned ``extension_key``s — **not** on the assets table.

Failure isolation is **per key**: each extension provisions inside its own savepoint;
a key whose factory raises is logged and skipped, and the keys that did succeed are
still recorded. A failure here never touches the already-committed asset.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import transaction

from app.detail_extensions.base.extension_factory import ExtensionFactory
from app.detail_extensions.control_layer.domain_structs.owner_enablement_struct import (
    OwnerEnablementStruct,
)
from app.detail_extensions.control_layer.guards.extension_registry_guard import (
    ExtensionRegistryValidator,
)
from app.detail_extensions.models.provisioning_state import (
    AssetExtensionProvisioningState,
)

if TYPE_CHECKING:
    from app.assets.models import Asset

logger = logging.getLogger(__name__)


class AssetExtensionProvisioner:
    """Provisions asset-target extension rows from the enablement tables."""

    @classmethod
    def provision_for_asset(cls, *, asset_id: int, actor_id: int | None = None) -> list:
        from app.assets.models import Asset

        asset = Asset.objects.filter(id=asset_id).first()
        if asset is None:
            logger.warning("Asset %s gone before provisioning; skipping.", asset_id)
            return []
        actor = cls._resolve_actor(actor_id)

        created: list = []
        with transaction.atomic():
            state, _ = AssetExtensionProvisioningState.objects.get_or_create(
                asset=asset,
                defaults={"created_by": actor, "updated_by": actor},
            )
            already = set(state.provisioned_keys or [])
            newly: list[str] = []

            for extension_key in cls._enabled_keys(asset):
                if extension_key in already:
                    continue
                try:
                    with transaction.atomic():  # per-key savepoint
                        descriptor = ExtensionRegistryValidator.resolve(extension_key)
                        factory = descriptor.factory or ExtensionFactory
                        created.append(
                            factory.provision(
                                owner=asset, descriptor=descriptor, actor=actor
                            )
                        )
                    newly.append(extension_key)
                except Exception:
                    logger.exception(
                        "Provisioning extension '%s' for asset %s failed; skipped.",
                        extension_key,
                        asset_id,
                    )

            if newly:
                state.provisioned_keys = sorted(already.union(newly))
                state.updated_by = actor
                state.save(
                    update_fields=["provisioned_keys", "updated_by", "updated_at"]
                )
        return created

    @staticmethod
    def _resolve_actor(actor_id: int | None):
        if actor_id is None:
            return None
        return get_user_model().objects.filter(pk=actor_id).first()

    @staticmethod
    def _enabled_keys(asset: "Asset") -> list[str]:
        """Class- + model-level enabled keys, resolved by the shared struct."""
        return OwnerEnablementStruct.for_asset(asset).sorted_keys()
