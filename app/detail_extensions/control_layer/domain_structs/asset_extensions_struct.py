"""AssetExtensionsStruct — one gathered read of every asset-target extension's rows.

Registry-driven union across heterogeneous extension tables. Read-only;
``to_dict()`` for rendering.
"""

from __future__ import annotations

from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import ExtensionTarget


class AssetExtensionsStruct:
    def __init__(self, asset_id: int) -> None:
        self.asset_id = asset_id
        # {extension_key: [row, ...]} across every asset-target extension table.
        self.rows_by_extension: dict[str, list] = {}
        for descriptor in registry.descriptors_for_target(ExtensionTarget.ASSET):
            self.rows_by_extension[descriptor.key] = list(
                descriptor.primary_model.objects.filter(asset_id=asset_id)
            )

    def to_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "extensions": {
                key: [self._row_to_dict(row) for row in rows]
                for key, rows in self.rows_by_extension.items()
            },
        }

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            field.name: getattr(row, field.attname, None)
            for field in row._meta.fields
        }
