"""ModelExtensionsStruct — gathered read of every model-target extension's rows."""

from __future__ import annotations

from app.detail_extensions import registry
from app.detail_extensions.base.extension_descriptor import ExtensionTarget


class ModelExtensionsStruct:
    def __init__(self, model_id: int) -> None:
        self.model_id = model_id
        self.rows_by_extension: dict[str, list] = {}
        for descriptor in registry.descriptors_for_target(ExtensionTarget.MODEL):
            self.rows_by_extension[descriptor.key] = list(
                descriptor.primary_model.objects.filter(model_id=model_id)
            )

    def to_dict(self) -> dict:
        return {
            "model_id": self.model_id,
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
