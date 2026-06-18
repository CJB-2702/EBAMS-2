"""ModelExtensionProvisioner — provisions enabled model extensions for one model.

Mirror of ``AssetExtensionProvisioner`` for model-target extensions. Enablement is
scoped by asset class (``model_detail_extensions_by_asset_class``). Runs post-commit in
its own transaction; idempotency is tracked in ``ModelExtensionProvisioningState``
(E7). Per-key savepoint isolation; failures are logged and skipped.
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
    ModelExtensionProvisioningState,
)

if TYPE_CHECKING:
    from app.assets.models import AssetModel

logger = logging.getLogger(__name__)


class ModelExtensionProvisioner:
    """Provisions model-target extension rows from the enablement table."""

    @classmethod
    def provision_for_model(cls, *, model_id: int, actor_id: int | None = None) -> list:
        from app.assets.models import AssetModel

        model = AssetModel.objects.filter(id=model_id).first()
        if model is None:
            logger.warning("AssetModel %s gone before provisioning; skipping.", model_id)
            return []
        actor = cls._resolve_actor(actor_id)

        created: list = []
        with transaction.atomic():
            state, _ = ModelExtensionProvisioningState.objects.get_or_create(
                model=model,
                defaults={"created_by": actor, "updated_by": actor},
            )
            already = set(state.provisioned_keys or [])
            newly: list[str] = []

            for extension_key in cls._enabled_keys(model):
                if extension_key in already:
                    continue
                try:
                    with transaction.atomic():  # per-key savepoint
                        descriptor = ExtensionRegistryValidator.resolve(extension_key)
                        factory = descriptor.factory or ExtensionFactory
                        created.append(
                            factory.provision(
                                owner=model, descriptor=descriptor, actor=actor
                            )
                        )
                    newly.append(extension_key)
                except Exception:
                    logger.exception(
                        "Provisioning extension '%s' for model %s failed; skipped.",
                        extension_key,
                        model_id,
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
    def _enabled_keys(model: "AssetModel") -> list[str]:
        """Class-level model-extension keys, resolved by the shared struct."""
        return OwnerEnablementStruct.for_model(model).sorted_keys()
