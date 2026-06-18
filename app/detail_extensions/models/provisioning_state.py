"""Provisioning-state tables — durable markers of what has been provisioned.

One row per owner (OneToOne), holding the list of ``extension_key``s already
provisioned. This is the **idempotency / backfill** marker (E7): absence of a row
means "never provisioned", and a key in ``provisioned_keys`` means "done".

Why a durable marker is still required: a ``ONE_TO_MANY`` extension (e.g. smog
history) with zero rows is a *valid* provisioned state, so row-existence alone cannot
distinguish "provisioned, empty" from "never provisioned." The key list disambiguates.

The FK points ``detail_extensions → assets`` — the one allowed direction. The assets
tables carry **no** extension state.
"""

from django.db import models

from app.administration.models.auditable_mixin import AuditFieldsMixin


class AssetExtensionProvisioningState(AuditFieldsMixin):
    """Which extension_keys have been provisioned for one asset."""

    asset = models.OneToOneField(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="extension_provisioning_state",
    )
    provisioned_keys = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "asset_extension_provisioning_state"

    def __str__(self) -> str:
        return f"AssetExtensionProvisioningState asset={self.asset_id}"


class ModelExtensionProvisioningState(AuditFieldsMixin):
    """Which extension_keys have been provisioned for one asset model."""

    model = models.OneToOneField(
        "assets.AssetModel",
        on_delete=models.CASCADE,
        related_name="extension_provisioning_state",
    )
    provisioned_keys = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "model_extension_provisioning_state"

    def __str__(self) -> str:
        return f"ModelExtensionProvisioningState model={self.model_id}"
